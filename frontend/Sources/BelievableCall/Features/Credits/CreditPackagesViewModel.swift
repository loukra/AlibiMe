import Foundation
import Observation

/// Drives the Add Credits bottom sheet: loads the backend package catalog,
/// tracks the selection, buys paid packs through the App Store and has the
/// backend verify and grant them. The backend remains the source of truth for
/// the resulting balance.
@MainActor
@Observable
public final class CreditPackagesViewModel: Identifiable {
    /// Explicit sheet state machine (mirrors the feature spec).
    public enum Phase: Equatable {
        case idle
        case loadingPackages
        case ready
        case submitting
        case success
        case failure
    }

    public private(set) var phase: Phase = .idle
    public private(set) var packages: [CreditPackage] = []
    public var selectedCode: String?
    public private(set) var errorMessage: String?
    public private(set) var lastGranted: CreditAcquisition?
    public private(set) var costs: CreditCosts?
    public private(set) var firstPurchaseBonus = 0
    /// Localized App Store prices by product id, once StoreKit has them.
    public private(set) var storePrices: [String: String] = [:]
    /// Set while a purchase waits for approval (Ask to Buy).
    public private(set) var pendingNotice: String?

    private let service: CreditPackagesServicing
    private let purchases: PurchaseServicing
    private let accountToken: UUID?
    public var onSessionExpired: (() -> Void)?

    public init(service: CreditPackagesServicing,
                purchases: PurchaseServicing = MockPurchaseService(),
                accountToken: UUID? = nil) {
        self.service = service
        self.purchases = purchases
        self.accountToken = accountToken
    }

    /// The store's localized price when known, else the backend's label.
    public func price(for package: CreditPackage) -> String {
        package.storeProductID.flatMap { storePrices[$0] } ?? package.priceLabel
    }

    /// "A call uses 2 credits, a text 1."
    public var costsNote: String? {
        guard let costs else { return nil }
        return "A call uses \(costs.call) credits, a text \(costs.text)."
    }

    /// "+3 bonus credits on your first purchase", while it still applies.
    public var bonusNote: String? {
        guard firstPurchaseBonus > 0, packages.contains(where: \.isStorePurchase) else { return nil }
        return "+\(firstPurchaseBonus) bonus credits on your first purchase"
    }

    public var selectedPackage: CreditPackage? {
        guard let selectedCode else { return nil }
        return packages.first { $0.code == selectedCode }
    }

    public var canSubmit: Bool {
        selectedPackage != nil && phase != .submitting
    }

    public var isSubmitting: Bool { phase == .submitting }

    /// Distinguishes a catalog-load failure (offer retry) from an acquisition
    /// failure (packages still shown, selection preserved).
    public var didFailToLoad: Bool { phase == .failure && packages.isEmpty }
    public var isEmptyCatalog: Bool { phase == .ready && packages.isEmpty }

    public var primaryButtonTitle: String {
        if let pkg = selectedPackage {
            return pkg.isStorePurchase ? "Buy \(pkg.credits) Credits for \(price(for: pkg))" : "Add \(pkg.credits) Credits"
        }
        return "Add Credits"
    }

    public func load() async {
        phase = .loadingPackages
        errorMessage = nil
        do {
            let catalog = try await service.catalog()
            let list = catalog.packages
            packages = list
            costs = catalog.costs
            firstPurchaseBonus = catalog.firstPurchaseBonus
            let productIDs = list.compactMap(\.storeProductID)
            if !productIDs.isEmpty {
                storePrices = await purchases.prices(for: productIDs)
            }
            // Preserve a still-valid selection, else default to the first pack.
            if selectedCode == nil || !list.contains(where: { $0.code == selectedCode }) {
                selectedCode = list.first?.code
            }
            phase = .ready
        } catch {
            handle(error)
        }
    }

    public func select(_ code: String) {
        guard phase != .submitting else { return }
        selectedCode = code
        // Clear a stale acquisition error once the user changes intent.
        if phase == .failure { errorMessage = nil; phase = .ready }
    }

    /// Acquires the selected package. Returns `true` on success so the caller can
    /// dismiss the sheet and refresh the outer screen. Double-submits are guarded
    /// by `phase == .submitting` and backend idempotency.
    @discardableResult
    public func acquire() async -> Bool {
        guard let pkg = selectedPackage, phase != .submitting else { return false }
        phase = .submitting
        errorMessage = nil
        pendingNotice = nil
        do {
            let result: CreditAcquisition
            if pkg.isStorePurchase, let productID = pkg.storeProductID {
                switch try await purchases.purchase(productID: productID, accountToken: accountToken) {
                case let .purchased(purchase):
                    result = try await service.redeem(signedTransaction: purchase.signedTransaction)
                    // Only finish once the credits are ours; an unfinished
                    // transaction is redeemed again on the next launch.
                    await purchases.finish(transactionID: purchase.transactionID)
                case .cancelled:
                    phase = .ready
                    return false
                case .pending:
                    pendingNotice = "Waiting for approval. The credits arrive once it's approved."
                    phase = .ready
                    return false
                }
            } else {
                result = try await service.acquire(code: pkg.code, clientRequestID: UUID().uuidString)
            }
            lastGranted = result
            phase = .success
            return true
        } catch PurchaseError.productUnavailable {
            errorMessage = "This pack isn't available in the App Store right now."
            phase = .failure
            return false
        } catch {
            handle(error)
            return false
        }
    }

    private func handle(_ error: Error) {
        let apiError = asAPIError(error)
        if apiError.requiresReauth {
            onSessionExpired?()
            phase = .failure
            return
        }
        errorMessage = ErrorCopy.userMessage(for: apiError)
        phase = .failure
    }
}
