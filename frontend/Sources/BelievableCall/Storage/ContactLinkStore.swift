import Foundation

/// Local, on-device record of whether the user has saved a sender as a contact,
/// keyed by `sender_binding_id`. This is intentionally device-local: per the
/// feature spec, iOS contact identifiers never go to the backend, and sender
/// continuity comes from the backend binding regardless of this state.
public protocol ContactLinkStoring: AnyObject, Sendable {
    func state(forBinding bindingID: String) -> ContactLinkState?
    func save(_ state: ContactLinkState)
}

public extension ContactLinkStoring {
    /// Whether the post-success Save Contact prompt should be offered for this
    /// binding (only the first time it is seen, until created/dismissed/denied).
    func shouldOfferPrompt(forBinding bindingID: String) -> Bool {
        state(forBinding: bindingID)?.shouldOfferPrompt ?? true
    }
}

public final class UserDefaultsContactLinkStore: ContactLinkStoring, @unchecked Sendable {
    private let defaults: UserDefaults
    private let keyPrefix = "bc.contactLink."

    public init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    private func key(_ bindingID: String) -> String { keyPrefix + bindingID }

    public func state(forBinding bindingID: String) -> ContactLinkState? {
        guard let data = defaults.data(forKey: key(bindingID)) else { return nil }
        return try? JSONDecoder().decode(ContactLinkState.self, from: data)
    }

    public func save(_ state: ContactLinkState) {
        guard let data = try? JSONEncoder().encode(state) else { return }
        defaults.set(data, forKey: key(state.senderBindingID))
    }
}

/// In-memory store for tests and previews.
public final class InMemoryContactLinkStore: ContactLinkStoring, @unchecked Sendable {
    private var states: [String: ContactLinkState] = [:]
    public init() {}
    public func state(forBinding bindingID: String) -> ContactLinkState? { states[bindingID] }
    public func save(_ state: ContactLinkState) { states[state.senderBindingID] = state }
}
