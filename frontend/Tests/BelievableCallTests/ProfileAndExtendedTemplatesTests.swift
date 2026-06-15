import XCTest
@testable import BelievableCall

@MainActor
final class ProfileViewModelTests: XCTestCase {
    func testLoadPopulatesProfileAndOptions() async {
        let vm = ProfileViewModel(service: MockContextProfileService(),
                                  templates: MockTemplateService())
        await vm.load()
        XCTAssertEqual(vm.phase, .ready)
        XCTAssertFalse(vm.options.workSettings.isEmpty)
    }

    func testSavePersistsAndFlags() async {
        let service = MockContextProfileService()
        let vm = ProfileViewModel(service: service, templates: MockTemplateService())
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
        let vm = ProfileViewModel(service: service, templates: MockTemplateService())
        await vm.load()
        await vm.clearAll()
        XCTAssertFalse(vm.profile.hasAnyContext)
        XCTAssertNil(service.profile.workSetting)
    }

    func testSessionExpiredRoutes() async {
        let service = MockContextProfileService()
        service.error = APIError.sessionExpired
        let vm = ProfileViewModel(service: service, templates: MockTemplateService())
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
        XCTAssertFalse(vm.draft.persona.isEmpty)
        // Rich defaults are valid coded values.
        XCTAssertEqual(vm.draft.outcome, "step_out_briefly")
        XCTAssertEqual(vm.draft.continuityScope, "one_off")
    }

    func testCreateSendsRichDraft() async {
        let service = MockTemplateService()
        let vm = CustomTemplateEditorViewModel(service: service)
        await vm.load()
        vm.draft.displayName = "Leave the date"
        vm.draft.outcome = "leave_now"
        vm.draft.contextModules = ["home"]
        let created = await vm.submit()
        XCTAssertNotNil(created)
        XCTAssertTrue(created?.isCustom == true)
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
