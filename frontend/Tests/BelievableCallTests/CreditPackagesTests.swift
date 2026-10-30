import XCTest
@testable import BelievableCall

@MainActor
final class CreditPackagesViewModelTests: XCTestCase {
    private let devPack = CreditPackage(code: "dev_5", displayName: "5 Credits", credits: 5,
                                        fulfillmentMode: "free_dev", priceLabel: "Free for now",
                                        badgeText: nil, sortOrder: 1)

    func testLoadPopulatesPackagesCostsAndSelectsFirst() async {
        let vm = CreditPackagesViewModel(service: MockCreditPackagesService())
        await vm.load()
        XCTAssertEqual(vm.phase, .ready)
        XCTAssertEqual(vm.packages.count, 3)
        XCTAssertEqual(vm.selectedCode, "credits_10")
        XCTAssertEqual(vm.primaryButtonTitle, "Buy 10 Credits for €4.99")
        XCTAssertEqual(vm.costsNote, "A call uses 2 credits, a text 1.")
        XCTAssertTrue(vm.canSubmit)
    }

    func testStorePriceReplacesBackendLabel() async {
        let purchases = MockPurchaseService(storePrices: ["com.believablecall.app.credits25": "9,99 €"])
        let vm = CreditPackagesViewModel(service: MockCreditPackagesService(), purchases: purchases)
        await vm.load()
        vm.select("credits_25")
        XCTAssertEqual(vm.primaryButtonTitle, "Buy 25 Credits for 9,99 €")
        XCTAssertEqual(vm.price(for: vm.packages[0]), "€4.99")  // store doesn't know it
    }

    func testPurchaseIsRedeemedThenFinished() async {
        let service = MockCreditPackagesService(balance: 3)
        let purchases = MockPurchaseService()
        let vm = CreditPackagesViewModel(service: service, purchases: purchases)
        await vm.load()
        XCTAssertEqual(vm.bonusNote, "+3 bonus credits on your first purchase")
        vm.select("credits_25")
        let ok = await vm.acquire()
        XCTAssertTrue(ok)
        XCTAssertEqual(vm.phase, .success)
        XCTAssertEqual(vm.lastGranted?.grantedCredits, 28)  // 25 + first-purchase bonus
        XCTAssertEqual(vm.lastGranted?.creditsAvailable, 31)
        XCTAssertEqual(service.redeemed.count, 1)
        XCTAssertTrue(service.redeemed[0].hasPrefix("mock:com.believablecall.app.credits25:"))
        XCTAssertEqual(purchases.finished.count, 1)
        XCTAssertTrue(service.acquiredCodes.isEmpty)  // never the free path
    }

    func testFailedRedeemLeavesTransactionUnfinished() async {
        let service = MockCreditPackagesService()
        service.acquireError = APIError.transport(message: "offline")
        let purchases = MockPurchaseService()
        let vm = CreditPackagesViewModel(service: service, purchases: purchases)
        await vm.load()
        let ok = await vm.acquire()
        XCTAssertFalse(ok)
        XCTAssertTrue(purchases.finished.isEmpty)  // redeemed again on next launch
        XCTAssertNotNil(vm.errorMessage)
    }

    func testCancelledPurchaseIsQuiet() async {
        let purchases = MockPurchaseService()
        purchases.outcome = .cancelled
        let vm = CreditPackagesViewModel(service: MockCreditPackagesService(), purchases: purchases)
        await vm.load()
        let ok = await vm.acquire()
        XCTAssertFalse(ok)
        XCTAssertEqual(vm.phase, .ready)
        XCTAssertNil(vm.errorMessage)
    }

    func testPendingPurchaseExplains() async {
        let purchases = MockPurchaseService()
        purchases.outcome = .pending
        let vm = CreditPackagesViewModel(service: MockCreditPackagesService(), purchases: purchases)
        await vm.load()
        _ = await vm.acquire()
        XCTAssertEqual(vm.phase, .ready)
        XCTAssertNotNil(vm.pendingNotice)
    }

    func testFreeDevPackStillUsesAcquire() async {
        let service = MockCreditPackagesService(packages: [devPack], balance: 3)
        let vm = CreditPackagesViewModel(service: service)
        await vm.load()
        XCTAssertNil(vm.bonusNote)  // free dev packs carry no store bonus
        XCTAssertEqual(vm.primaryButtonTitle, "Add 5 Credits")
        let ok = await vm.acquire()
        XCTAssertTrue(ok)
        XCTAssertEqual(service.acquiredCodes, ["dev_5"])
        XCTAssertEqual(vm.lastGranted?.creditsAvailable, 8)
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
        vm.select("credits_25")
        service.acquireError = APIError.api(code: "rate_limited", message: "slow down",
                                            retryable: true, requestID: nil)
        let ok = await vm.acquire()
        XCTAssertFalse(ok)
        XCTAssertEqual(vm.phase, .failure)
        XCTAssertFalse(vm.packages.isEmpty)
        XCTAssertEqual(vm.selectedCode, "credits_25")
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
