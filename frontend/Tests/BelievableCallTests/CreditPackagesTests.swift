import XCTest
@testable import BelievableCall

@MainActor
final class CreditPackagesViewModelTests: XCTestCase {
    func testLoadPopulatesPackagesAndSelectsFirst() async {
        let vm = CreditPackagesViewModel(service: MockCreditPackagesService())
        await vm.load()
        XCTAssertEqual(vm.phase, .ready)
        XCTAssertEqual(vm.packages.count, 4)
        XCTAssertEqual(vm.selectedCode, "credits_5")
        XCTAssertEqual(vm.primaryButtonTitle, "Add 5 Credits")
        XCTAssertTrue(vm.canSubmit)
    }

    func testSelectUpdatesPrimaryButton() async {
        let vm = CreditPackagesViewModel(service: MockCreditPackagesService())
        await vm.load()
        vm.select("credits_30")
        XCTAssertEqual(vm.selectedCode, "credits_30")
        XCTAssertEqual(vm.primaryButtonTitle, "Add 30 Credits")
    }

    func testAcquireGrantsAndReportsBalance() async {
        let service = MockCreditPackagesService(balance: 3)
        let vm = CreditPackagesViewModel(service: service)
        await vm.load()
        vm.select("credits_15")
        let ok = await vm.acquire()
        XCTAssertTrue(ok)
        XCTAssertEqual(vm.phase, .success)
        XCTAssertEqual(vm.lastGranted?.grantedCredits, 15)
        XCTAssertEqual(vm.lastGranted?.creditsAvailable, 18)
        XCTAssertEqual(service.acquiredCodes, ["credits_15"])
    }

    func testLoadFailureSurfacesRetryState() async {
        let service = MockCreditPackagesService()
        service.listError = APIError.unexpectedStatus(503)
        let vm = CreditPackagesViewModel(service: service)
        await vm.load()
        XCTAssertEqual(vm.phase, .failure)
        XCTAssertTrue(vm.didFailToLoad)
        XCTAssertNotNil(vm.errorMessage)
    }

    func testAcquireFailureKeepsPackagesAndSelection() async {
        let service = MockCreditPackagesService()
        let vm = CreditPackagesViewModel(service: service)
        await vm.load()
        vm.select("credits_15")
        service.acquireError = APIError.api(code: "rate_limited", message: "slow down",
                                            retryable: true, requestID: nil)
        let ok = await vm.acquire()
        XCTAssertFalse(ok)
        XCTAssertEqual(vm.phase, .failure)
        XCTAssertFalse(vm.packages.isEmpty)          // sheet stays usable
        XCTAssertEqual(vm.selectedCode, "credits_15") // selection preserved
        XCTAssertNotNil(vm.errorMessage)
    }

    func testEmptyCatalogState() async {
        let vm = CreditPackagesViewModel(service: MockCreditPackagesService(packages: []))
        await vm.load()
        XCTAssertEqual(vm.phase, .ready)
        XCTAssertTrue(vm.isEmptyCatalog)
        XCTAssertNil(vm.selectedCode)
        XCTAssertFalse(vm.canSubmit)
    }

    func testSessionExpiredRoutesToCallback() async {
        let service = MockCreditPackagesService()
        service.listError = APIError.sessionExpired
        let vm = CreditPackagesViewModel(service: service)
        var expired = false
        vm.onSessionExpired = { expired = true }
        await vm.load()
        XCTAssertTrue(expired)
    }
}
