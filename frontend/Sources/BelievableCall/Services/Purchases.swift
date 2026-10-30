import Foundation
#if canImport(StoreKit)
import StoreKit
#endif

/// A finished App Store purchase, ready to send to the backend.
public struct StorePurchase: Equatable, Sendable {
    /// StoreKit 2's JWS; the backend checks Apple's signature before granting.
    public let signedTransaction: String
    public let transactionID: String

    public init(signedTransaction: String, transactionID: String) {
        self.signedTransaction = signedTransaction
        self.transactionID = transactionID
    }
}

public enum PurchaseOutcome: Equatable, Sendable {
    case purchased(StorePurchase)
    case cancelled
    /// Waiting for Ask to Buy or similar; the transaction arrives later.
    case pending
}

/// Buying credit packs. The real one talks to StoreKit; the mock lets the whole
/// flow run in the simulator and tests without App Store Connect.
public protocol PurchaseServicing: Sendable {
    /// Localized prices ("2,99 €") by product id, for the products the store knows.
    func prices(for productIDs: [String]) async -> [String: String]
    /// `accountToken` ties the purchase to our user, so the backend can refuse
    /// a transaction replayed from another account.
    func purchase(productID: String, accountToken: UUID?) async throws -> PurchaseOutcome
    /// Called once the backend has granted the credits.
    func finish(transactionID: String) async
    /// Purchases StoreKit delivered but we never finished (app killed mid-way,
    /// Ask to Buy approved later). Redeemed on launch.
    func unfinished() async -> [StorePurchase]
    /// Purchases that arrive while the app runs but outside `purchase`
    /// (Ask to Buy approved, bought on another device).
    func updates() -> AsyncStream<StorePurchase>
}

public enum PurchaseError: Error, Equatable {
    case productUnavailable
    case unverified
    /// StoreKit threw: the purchase did not go through.
    case storeFailed
}

public final class MockPurchaseService: PurchaseServicing, @unchecked Sendable {
    public var outcome: PurchaseOutcome?
    /// Thrown by `purchase`, as StoreKit does when a purchase fails.
    public var purchaseError: Error?
    public var storePrices: [String: String]
    public private(set) var finished: [String] = []
    public private(set) var purchased: [String] = []
    public var pending: [StorePurchase] = []

    public init(storePrices: [String: String] = [:]) { self.storePrices = storePrices }

    public func prices(for productIDs: [String]) async -> [String: String] { storePrices }

    public func purchase(productID: String, accountToken: UUID?) async throws -> PurchaseOutcome {
        purchased.append(productID)
        if let purchaseError { throw purchaseError }
        if let outcome { return outcome }
        let id = UUID().uuidString
        return .purchased(StorePurchase(signedTransaction: "mock:\(productID):\(id)", transactionID: id))
    }

    public func finish(transactionID: String) async { finished.append(transactionID) }

    public func unfinished() async -> [StorePurchase] { pending }

    public func updates() -> AsyncStream<StorePurchase> { AsyncStream { $0.finish() } }
}

#if canImport(StoreKit)
public final class StoreKitPurchaseService: PurchaseServicing, @unchecked Sendable {
    public init() {}

    public func prices(for productIDs: [String]) async -> [String: String] {
        guard let products = try? await Product.products(for: productIDs) else { return [:] }
        return Dictionary(uniqueKeysWithValues: products.map { ($0.id, $0.displayPrice) })
    }

    public func purchase(productID: String, accountToken: UUID?) async throws -> PurchaseOutcome {
        guard let product = try await Product.products(for: [productID]).first else {
            throw PurchaseError.productUnavailable
        }
        var options: Set<Product.PurchaseOption> = []
        if let accountToken { options.insert(.appAccountToken(accountToken)) }
        switch try await product.purchase(options: options) {
        case let .success(result):
            guard case let .verified(transaction) = result else { throw PurchaseError.unverified }
            return .purchased(StorePurchase(signedTransaction: result.jwsRepresentation,
                                            transactionID: String(transaction.id)))
        case .pending:
            return .pending
        case .userCancelled:
            return .cancelled
        @unknown default:
            return .cancelled
        }
    }

    public func finish(transactionID: String) async {
        for await result in Transaction.unfinished {
            if case let .verified(transaction) = result, String(transaction.id) == transactionID {
                await transaction.finish()
            }
        }
    }

    public func unfinished() async -> [StorePurchase] {
        var out: [StorePurchase] = []
        for await result in Transaction.unfinished {
            if case let .verified(transaction) = result, transaction.productType == .consumable {
                out.append(StorePurchase(signedTransaction: result.jwsRepresentation,
                                         transactionID: String(transaction.id)))
            }
        }
        return out
    }

    public func updates() -> AsyncStream<StorePurchase> {
        AsyncStream { continuation in
            let task = Task {
                for await result in Transaction.updates {
                    if case let .verified(transaction) = result, transaction.productType == .consumable {
                        continuation.yield(StorePurchase(signedTransaction: result.jwsRepresentation,
                                                         transactionID: String(transaction.id)))
                    }
                }
                continuation.finish()
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }
}
#endif
