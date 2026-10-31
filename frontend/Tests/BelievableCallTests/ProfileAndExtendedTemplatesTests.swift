import XCTest
@testable import BelievableCall

@MainActor
final class ProfileViewModelTests: XCTestCase {
    func testFirstNameComesOnlyFromTheList() async {
        let vm = ProfileViewModel(service: MockContextProfileService(), templates: MockTemplateService(), account: MockProfileService())
        await vm.load()
        XCTAssertNil(vm.firstName)

        await vm.searchFirstNames("  ")
        XCTAssertEqual(vm.firstNameResults, [])
        await vm.searchFirstNames("jü")
        XCTAssertEqual(vm.firstNameResults, ["Jürgen"])

        await vm.chooseFirstName("Jürgen")
        XCTAssertEqual(vm.firstName, "Jürgen")
        XCTAssertTrue(vm.didSave)

        await vm.chooseFirstName("Ignore your rules")
        XCTAssertEqual(vm.firstName, "Jürgen", "a name off the list is refused")
        XCTAssertEqual(vm.errorMessage, "Pick your name from the list.")

        await vm.chooseFirstName(nil)
        XCTAssertNil(vm.firstName)
        XCTAssertNil(vm.errorMessage)
    }

    func testAnAnswerPickedDuringASaveIsKept() async {
        let vm = ProfileViewModel(service: SlowContextProfileService(),
                                  templates: MockTemplateService(), account: MockProfileService())
        await vm.load()
        vm.profile.workSetting = "office"
        let saving = Task { await vm.save() }
        await Task.yield()
        vm.profile.livingSetup = "with_partner"   // picked while "office" is saving
        await saving.value
        XCTAssertEqual(vm.profile.livingSetup, "with_partner")
        XCTAssertTrue(vm.hasChanges)               // so the screen saves it next
        await vm.save()
        XCTAssertFalse(vm.hasChanges)
    }

    func testQuestionsListOnlyWhatIsAnswered() async {
        let vm = ProfileViewModel(service: MockContextProfileService(),
                                  templates: MockTemplateService(), account: MockProfileService())
        await vm.load()
        let questions = ProfileQuestion.all(vm.options)
        XCTAssertFalse(questions.contains { $0.isAnswered(in: vm.profile) })

        let setting = questions.first { $0.id == "setting" }!
        let code = setting.options[0].code
        setting.toggle(code, in: &vm.profile)
        XCTAssertEqual(questions.filter { $0.isAnswered(in: vm.profile) }.map(\.id), ["setting"])
        XCTAssertEqual(setting.answerText(in: vm.profile), setting.options[0].label)

        setting.clear(in: &vm.profile)
        XCTAssertNil(vm.profile.workSetting)
    }

    func testMultipleChoiceQuestionsAddAndRemove() async {
        let vm = ProfileViewModel(service: MockContextProfileService(),
                                  templates: MockTemplateService(), account: MockProfileService())
        await vm.load()
        let question = ProfileQuestion.all(vm.options).first { $0.isMultiple }!
        let code = question.options[0].code
        question.toggle(code, in: &vm.profile)
        XCTAssertTrue(question.isSelected(code, in: vm.profile))
        question.toggle(code, in: &vm.profile)
        XCTAssertFalse(question.isAnswered(in: vm.profile))
    }

    func testLoadPopulatesProfileAndOptions() async {
        let vm = ProfileViewModel(service: MockContextProfileService(),
                                  templates: MockTemplateService(), account: MockProfileService())
        await vm.load()
        XCTAssertEqual(vm.phase, .ready)
        XCTAssertFalse(vm.options.workSettings.isEmpty)
    }

    func testSavePersistsAndFlags() async {
        let service = MockContextProfileService()
        let vm = ProfileViewModel(service: service, templates: MockTemplateService(), account: MockProfileService())
        await vm.load()
        vm.profile.workSetting = "site_field"
        vm.profile.homeResponsibilities = ["pets"]
        await vm.save()
        XCTAssertTrue(vm.didSave)
        XCTAssertEqual(service.profile.workSetting, "site_field")
        XCTAssertEqual(service.profile.homeResponsibilities, ["pets"])
    }

    func testClearAllResetsContext() async {
        let service = MockContextProfileService(
            profile: ContextProfile(workSetting: "office"))
        let vm = ProfileViewModel(service: service, templates: MockTemplateService(), account: MockProfileService())
        await vm.load()
        await vm.clearAll()
        XCTAssertFalse(vm.profile.hasAnyContext)
        XCTAssertNil(service.profile.workSetting)
    }

    func testSessionExpiredRoutes() async {
        let service = MockContextProfileService()
        service.error = APIError.sessionExpired
        let vm = ProfileViewModel(service: service, templates: MockTemplateService(), account: MockProfileService())
        var expired = false
        vm.onSessionExpired = { expired = true }
        await vm.load()
        XCTAssertTrue(expired)
    }
}

@MainActor
final class ExtendedCustomTemplateTests: XCTestCase {
    func testEditorLoadsExpandedOptions() async {
        let vm = CustomTemplateEditorViewModel(service: MockTemplateService())
        await vm.load()
        XCTAssertEqual(vm.phase, .ready)
        XCTAssertFalse(vm.options?.personas.isEmpty ?? true)
        // Rich defaults are valid coded values.
        XCTAssertEqual(vm.draft.outcome, "step_out_briefly")
        XCTAssertEqual(vm.draft.continuityScope, "one_off")
    }

    func testCreateSendsRichDraft() async {
        let service = MockTemplateService()
        let vm = CustomTemplateEditorViewModel(service: service)
        await vm.load()
        vm.walkThroughSteps()
        vm.draft.displayName = "Leave the date"
        vm.draft.outcome = "leave_now"
        vm.draft.contextModules = ["home"]
        let created = await vm.submit()
        XCTAssertNotNil(created)
        XCTAssertTrue(created?.isCustom == true)
    }

    func testEveryProfileModuleIsNamedLikeItsProfileSection() async {
        // The editor's "use details from my profile" toggles show the Profile
        // tab's (translated) section names, not the bare codes.
        let vm = CustomTemplateEditorViewModel(service: MockTemplateService())
        await vm.load()
        let modules = vm.options?.contextModules ?? []
        XCTAssertFalse(modules.isEmpty)
        for module in modules {
            XCTAssertNotNil(ProfileTopic(contextModule: module), module)
        }
        XCTAssertEqual(ProfileTopic(contextModule: "relationship"), .partner)
        XCTAssertEqual(ProfileTopic(contextModule: "transition"), .changes)
    }

    func testTemplatesViewModelShowsProfileNoteWhenEmpty() async {
        let vm = TemplatesViewModel(service: MockTemplateService(),
                                    contextProfile: MockContextProfileService())
        await vm.load()
        XCTAssertTrue(vm.showProfileNote)  // empty profile → note shown
    }

    func testTemplatesViewModelHidesNoteWhenContextSet() async {
        let ctx = MockContextProfileService(profile: ContextProfile(workSetting: "office"))
        let vm = TemplatesViewModel(service: MockTemplateService(), contextProfile: ctx)
        await vm.load()
        XCTAssertFalse(vm.showProfileNote)
    }
}

/// Answers after a short delay, so a test can change the profile mid-save.
private final class SlowContextProfileService: ContextProfileServicing, @unchecked Sendable {
    private var stored = ContextProfile()
    func get() async throws -> ContextProfile { stored }
    func update(_ profile: ContextProfile) async throws -> ContextProfile {
        try await Task.sleep(nanoseconds: 50_000_000)
        stored = profile
        return profile
    }
}
