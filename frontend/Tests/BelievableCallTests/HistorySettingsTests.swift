import XCTest
@testable import BelievableCall

@MainActor
final class HistoryViewModelTests: XCTestCase {
    func testLoadPopulatesItems() async {
        let vm = HistoryViewModel(service: MockHistoryService())
        await vm.load()
        XCTAssertEqual(vm.items.count, Fixtures.history.count)
        XCTAssertFalse(vm.isEmpty)
    }

    func testEmptyStateWhenNoItems() async {
        let vm = HistoryViewModel(service: MockHistoryService(items: []))
        await vm.load()
        XCTAssertTrue(vm.isEmpty)
    }

    func testPaginationAppendsAndStops() async {
        let service = MockHistoryService(items: Fixtures.history, hasMore: true)
        let vm = HistoryViewModel(service: service, pageSize: 3)
        await vm.load()
        XCTAssertTrue(vm.hasMore)
        // Second page reports no more.
        service.page = HistoryPage(items: [Fixtures.history[0]], hasMore: false, nextOffset: 10)
        await vm.loadMore()
        XCTAssertEqual(vm.items.count, Fixtures.history.count + 1)
        XCTAssertFalse(vm.hasMore)
    }

    func testErrorMapsToCopy() async {
        let service = MockHistoryService()
        service.error = APIError.transport(message: "x")
        let vm = HistoryViewModel(service: service)
        await vm.load()
        XCTAssertNotNil(vm.errorMessage)
    }

    func testSessionExpiryRoutes() async {
        let service = MockHistoryService()
        service.error = APIError.sessionExpired
        let vm = HistoryViewModel(service: service)
        var expired = false
        vm.onSessionExpired = { expired = true }
        await vm.load()
        XCTAssertTrue(expired)
    }
}

@MainActor
final class SettingsViewModelTests: XCTestCase {
    func testLoadPopulatesFields() async {
        let vm = SettingsViewModel(profileService: MockProfileService(), auth: MockAuthService())
        await vm.load()
        XCTAssertEqual(vm.displayName, "Alex")
        XCTAssertEqual(vm.maskedNumber, "+14******123")
        XCTAssertEqual(vm.creditsAvailable, 3)
        XCTAssertEqual(vm.planLabel, "Free")
    }

    func testSaveUpdatesProfileAndFlagsSuccess() async {
        let profileService = MockProfileService()
        let vm = SettingsViewModel(profileService: profileService, auth: MockAuthService())
        await vm.load()
        vm.displayName = "Jordan"
        await vm.save()
        XCTAssertTrue(vm.didSave)
        XCTAssertEqual(vm.profile?.displayName, "Jordan")
    }

    func testSignOutInvokesCallback() async {
        let vm = SettingsViewModel(profileService: MockProfileService(), auth: MockAuthService())
        var signedOut = false
        vm.onSignOut = { signedOut = true }
        await vm.signOut()
        XCTAssertTrue(signedOut)
    }

    func testSaveErrorMapsToCopy() async {
        let profileService = MockProfileService()
        let vm = SettingsViewModel(profileService: profileService, auth: MockAuthService())
        await vm.load()
        profileService.error = APIError.api(code: "rate_limited", message: "x", retryable: true, requestID: nil)
        await vm.save()
        XCTAssertFalse(vm.didSave)
        XCTAssertNotNil(vm.errorMessage)
    }
}
