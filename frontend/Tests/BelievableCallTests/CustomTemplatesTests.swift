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
        editor.draft.displayName = "Temp"
        let created = await editor.submit()!

        let vm = TemplatesViewModel(service: service)
        await vm.load()
        await vm.delete(created)
        XCTAssertTrue(vm.customTemplates.isEmpty)
        XCTAssertEqual(service.deletedIDs, [created.id])
    }
}

@MainActor
final class CustomTemplateEditorViewModelTests: XCTestCase {
    func testLoadSetsDefaultsFromOptions() async {
        let vm = CustomTemplateEditorViewModel(service: MockTemplateService())
        await vm.load()
        XCTAssertEqual(vm.phase, .ready)
        XCTAssertFalse(vm.draft.persona.isEmpty)
        XCTAssertFalse(vm.draft.reason.isEmpty)
        XCTAssertEqual(vm.draft.callMaxSeconds, 60)
    }

    func testCannotSubmitWithoutName() async {
        let vm = CustomTemplateEditorViewModel(service: MockTemplateService())
        await vm.load()
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
        vm.draft.displayName = "X"
        let created = await vm.submit()
        XCTAssertNil(created)
        XCTAssertEqual(vm.phase, .failure)
        XCTAssertNotNil(vm.errorMessage)
    }
}
