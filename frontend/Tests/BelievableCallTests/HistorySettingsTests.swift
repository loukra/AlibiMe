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
        let vm = SettingsViewModel(profileService: MockProfileService(), auth: MockAuthService(), creditPackages: MockCreditPackagesService())
        await vm.load()
        XCTAssertEqual(vm.locale, "en")
        XCTAssertEqual(vm.maskedNumber, "+14******123")
        XCTAssertEqual(vm.creditsAvailable, 3)
    }

    func testSaveUpdatesProfileAndFlagsSuccess() async {
        let profileService = MockProfileService()
        let vm = SettingsViewModel(profileService: profileService, auth: MockAuthService(), creditPackages: MockCreditPackagesService())
        await vm.load()
        vm.locale = "de"
        await vm.save()
        XCTAssertTrue(vm.didSave)
        XCTAssertEqual(vm.profile?.locale, "de")
    }

    func testFirstNameComesOnlyFromTheList() async {
        let vm = SettingsViewModel(profileService: MockProfileService(), auth: MockAuthService(), creditPackages: MockCreditPackagesService())
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

    func testSavesOnlyWhatChanged() async {
        let profileService = MockProfileService()
        let vm = SettingsViewModel(profileService: profileService, auth: MockAuthService(), creditPackages: MockCreditPackagesService())
        await vm.load()
        XCTAssertFalse(vm.hasChanges)
        await vm.saveIfChanged()
        XCTAssertFalse(vm.didSave, "nothing changed, nothing sent")

        vm.locale = "de"
        XCTAssertTrue(vm.hasChanges)
        await vm.saveIfChanged()
        XCTAssertTrue(vm.didSave)
        XCTAssertEqual(vm.profile?.locale, "de")
        XCTAssertFalse(vm.hasChanges)
    }

    func testSignOutInvokesCallback() async {
        let vm = SettingsViewModel(profileService: MockProfileService(), auth: MockAuthService(), creditPackages: MockCreditPackagesService())
        var signedOut = false
        vm.onSignOut = { signedOut = true }
        await vm.signOut()
        XCTAssertTrue(signedOut)
    }

    func testSaveErrorMapsToCopy() async {
        let profileService = MockProfileService()
        let vm = SettingsViewModel(profileService: profileService, auth: MockAuthService(), creditPackages: MockCreditPackagesService())
        await vm.load()
        profileService.error = APIError.api(code: "rate_limited", message: "x", retryable: true, requestID: nil)
        await vm.save()
        XCTAssertFalse(vm.didSave)
        XCTAssertNotNil(vm.errorMessage)
    }

    func testDidAcquireCreditsSetsSuccessMessageAndRefreshes() async {
        let vm = SettingsViewModel(profileService: MockProfileService(),
                                   auth: MockAuthService(),
                                   creditPackages: MockCreditPackagesService())
        await vm.load()
        await vm.didAcquireCredits(
            CreditAcquisition(claimID: "c1", status: "granted", grantedCredits: 15,
                              creditsAvailable: 18, planCode: "credits_15")
        )
        XCTAssertEqual(vm.creditSuccessMessage, "15 credits added")
        // Balance reflects the backend (mock profile) after the refresh.
        XCTAssertEqual(vm.creditsAvailable, 3)
    }

    func testMakeCreditPackagesViewModelForwardsSessionExpiry() async {
        let vm = SettingsViewModel(profileService: MockProfileService(),
                                   auth: MockAuthService(),
                                   creditPackages: MockCreditPackagesService())
        var expired = false
        vm.onSessionExpired = { expired = true }
        let packagesVM = vm.makeCreditPackagesViewModel()
        packagesVM.onSessionExpired?()
        XCTAssertTrue(expired)
    }

    func testHelpAndPrivacyLinksPointAtTheBackend() {
        let vm = SettingsViewModel(profileService: MockProfileService(),
                                   auth: MockAuthService(),
                                   creditPackages: MockCreditPackagesService(),
                                   backendURL: URL(string: "https://api.alibime.test")!)
        XCTAssertEqual(vm.supportURL.absoluteString, "https://api.alibime.test/support?lang=\(AppLanguage.current)")
        XCTAssertEqual(vm.privacyURL.absoluteString, "https://api.alibime.test/privacy?lang=\(AppLanguage.current)")
    }
}
