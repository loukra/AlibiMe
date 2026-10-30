import XCTest
@testable import BelievableCall

@MainActor
final class TemplatesViewModelTests: XCTestCase {
    func testLoadSplitsSystemAndCustom() async {
        let service = MockTemplateService()
        let vm = TemplatesViewModel(service: service)
        await vm.load()
        XCTAssertFalse(vm.systemTemplates.isEmpty)
        XCTAssertTrue(vm.customTemplates.isEmpty)
    }

    func testCreateThenAppearsAsCustom() async {
        let service = MockTemplateService()
        let editor = CustomTemplateEditorViewModel(service: service)
        await editor.load()
        editor.walkThroughSteps()
        editor.draft.displayName = "My call"
        let created = await editor.submit()
        XCTAssertNotNil(created)
        XCTAssertTrue(created?.isCustom == true)

        let library = TemplatesViewModel(service: service)
        await library.load()
        XCTAssertEqual(library.customTemplates.count, 1)
        XCTAssertEqual(library.customTemplates.first?.displayName, "My call")
    }

    func testDeleteRemovesCustomTemplate() async {
        let service = MockTemplateService()
        let editor = CustomTemplateEditorViewModel(service: service)
        await editor.load()
        editor.walkThroughSteps()
        let created = await editor.submit()!

        let vm = TemplatesViewModel(service: service)
        await vm.load()
        await vm.delete(created)
        XCTAssertTrue(vm.customTemplates.isEmpty)
        XCTAssertEqual(service.deletedIDs, [created.id])
    }

    func testEditingABuiltInReplacesItAndResetBringsItBack() async throws {
        let service = MockTemplateService()
        let library = TemplatesViewModel(service: service)
        await library.load()
        let original = try XCTUnwrap(library.systemTemplates.first)

        let editor = library.makeEditorViewModel(editing: original)
        XCTAssertFalse(editor.canReset, "nothing to reset before the first edit")
        editor.draft.displayName = "My version"
        let savedResult = await editor.submit()
        let saved = try XCTUnwrap(savedResult)
        XCTAssertTrue(saved.isEdited)
        XCTAssertFalse(saved.isCustom)

        await library.editorFinished()
        XCTAssertTrue(library.systemTemplates.contains { $0.displayName == "My version" })
        XCTAssertFalse(library.systemTemplates.contains { $0.id == original.id })
        XCTAssertTrue(library.customTemplates.isEmpty)

        let again = library.makeEditorViewModel(editing: saved)
        XCTAssertTrue(again.canReset)
        XCTAssertFalse(again.canDelete)
        let removed = await again.remove()
        XCTAssertTrue(removed)
        await library.editorFinished()
        XCTAssertTrue(library.systemTemplates.contains { $0.id == original.id })
        XCTAssertFalse(library.systemTemplates.contains { $0.isEdited })
    }

    func testOwnTemplateEditsInPlaceAndCanBeDeletedFromTheEditor() async throws {
        let service = MockTemplateService()
        let create = CustomTemplateEditorViewModel(service: service)
        await create.load()
        create.walkThroughSteps()
        let createdResult = await create.submit()
        let created = try XCTUnwrap(createdResult)

        let edit = CustomTemplateEditorViewModel(service: service, editing: created)
        XCTAssertEqual(edit.step, .overview)
        XCTAssertEqual(edit.draft.persona, created.choices?.persona)
        edit.draft.displayName = "Renamed"
        let savedResult = await edit.submit()
        let saved = try XCTUnwrap(savedResult)
        XCTAssertEqual(saved.id, created.id)
        XCTAssertEqual(service.updated.map(\.id), [created.id])

        let delete = CustomTemplateEditorViewModel(service: service, editing: saved)
        XCTAssertTrue(delete.canDelete)
        XCTAssertFalse(delete.canReset)
        let removed = await delete.remove()
        XCTAssertTrue(removed)
        XCTAssertEqual(service.deletedIDs, [created.id])
    }
}

extension CustomTemplateEditorViewModel {
    /// Answers the three tile steps with the first option of each.
    func walkThroughSteps() {
        choosePersona(options!.personas[0].code)
        chooseReason(options!.reasons[0].code)
        chooseUrgency("high")
    }
}

@MainActor
final class CustomTemplateEditorViewModelTests: XCTestCase {
    func testNewTemplateWalksThroughTheSteps() async {
        let vm = CustomTemplateEditorViewModel(service: MockTemplateService())
        await vm.load()
        XCTAssertEqual(vm.phase, .ready)
        XCTAssertEqual(vm.step, .who)
        XCTAssertTrue(vm.draft.persona.isEmpty)
        XCTAssertFalse(vm.canSubmit)

        vm.choosePersona("roommate")
        XCTAssertEqual(vm.step, .why)
        // The persona's own group of reasons comes first.
        XCTAssertEqual(vm.reasonGroups.first?.title, "Home")

        vm.chooseReason("home_problem")
        XCTAssertEqual(vm.step, .urgency)
        XCTAssertEqual(vm.draft.category, "home_logistics")

        vm.chooseUrgency("immediate")
        XCTAssertEqual(vm.step, .overview)
        XCTAssertEqual(vm.draft.urgency, "immediate")
        XCTAssertEqual(vm.draft.displayName, "Roommate: a problem at home")
        XCTAssertEqual(vm.summary, "Your roommate calls about a problem at home.")
        XCTAssertEqual(vm.draft.callMaxSeconds, 60)
        XCTAssertTrue(vm.canSubmit)
    }

    func testChangingAnAnswerReturnsToTheOverview() async {
        let vm = CustomTemplateEditorViewModel(service: MockTemplateService())
        await vm.load()
        vm.walkThroughSteps()
        vm.go(to: .why)
        XCTAssertTrue(vm.canGoBack)
        vm.back()
        XCTAssertEqual(vm.step, .overview, "Back from a reopened step returns to the overview")
        vm.go(to: .why)
        vm.chooseReason("social_friend_outside")
        XCTAssertEqual(vm.step, .overview)
        XCTAssertEqual(vm.draft.category, "social_exit")
        // The suggested name was set once and is the user's now.
        XCTAssertEqual(vm.draft.displayName, "Manager: an urgent task")
    }

    func testBackGoesOneStep() async {
        let vm = CustomTemplateEditorViewModel(service: MockTemplateService())
        await vm.load()
        XCTAssertFalse(vm.canGoBack)
        vm.choosePersona("manager")
        XCTAssertTrue(vm.canGoBack)
        vm.back()
        XCTAssertEqual(vm.step, .who)
        XCTAssertEqual(vm.draft.persona, "manager")
    }

    func testTileLabelsDropTheArticle() {
        XCTAssertEqual(CustomTemplateEditorViewModel.tileLabel("your manager"), "Manager")
        XCTAssertEqual(CustomTemplateEditorViewModel.tileLabel("the office line"), "Office line")
        XCTAssertEqual(CustomTemplateEditorViewModel.tileLabel("someone you're seeing"),
                       "Someone you're seeing")
    }

    func testCannotSubmitWithoutName() async {
        let vm = CustomTemplateEditorViewModel(service: MockTemplateService())
        await vm.load()
        vm.walkThroughSteps()
        vm.draft.displayName = "   "
        XCTAssertFalse(vm.canSubmit)
        vm.draft.displayName = "Boss call"
        XCTAssertTrue(vm.canSubmit)
    }

    func testToggleChannels() async {
        let vm = CustomTemplateEditorViewModel(service: MockTemplateService())
        await vm.load()
        vm.toggle(.call, on: false)
        XCTAssertFalse(vm.draft.channels.contains(.call))
        vm.toggle(.call, on: true)
        XCTAssertTrue(vm.draft.channels.contains(.call))
    }

    func testSubmitFailureSurfacesError() async {
        let service = MockTemplateService()
        service.createError = APIError.api(code: "validation_failed", message: "bad",
                                           retryable: false, requestID: nil)
        let vm = CustomTemplateEditorViewModel(service: service)
        await vm.load()
        vm.walkThroughSteps()
        let created = await vm.submit()
        XCTAssertNil(created)
        XCTAssertEqual(vm.phase, .failure)
        XCTAssertNotNil(vm.errorMessage)
    }
}
