#if canImport(Contacts)
import Contacts

/// Live Contacts permission gateway over `CNContactStore`. Only ever requests
/// access in-context (when the user chooses to save a sender as a contact) —
/// never at launch — per the feature's privacy rules.
public struct LiveContactsService: ContactsServicing {
    public init() {}

    public func authorizationStatus() -> ContactAuthorization {
        Self.map(CNContactStore.authorizationStatus(for: .contacts))
    }

    public func requestAccess() async -> ContactAuthorization {
        // If already decided, don't re-prompt — just report the current state.
        let current = CNContactStore.authorizationStatus(for: .contacts)
        if current != .notDetermined {
            return Self.map(current)
        }
        let store = CNContactStore()
        let granted = await withCheckedContinuation { (cont: CheckedContinuation<Bool, Never>) in
            store.requestAccess(for: .contacts) { granted, _ in
                cont.resume(returning: granted)
            }
        }
        // Re-read rather than trust the bool, so we capture limited/restricted.
        let resolved = CNContactStore.authorizationStatus(for: .contacts)
        if resolved == .notDetermined {
            return granted ? .authorized : .denied
        }
        return Self.map(resolved)
    }

    static func map(_ status: CNAuthorizationStatus) -> ContactAuthorization {
        switch status {
        case .notDetermined: return .notDetermined
        case .restricted: return .restricted
        case .denied: return .denied
        case .authorized: return .authorized
        @unknown default:
            // `CNAuthorizationStatus.limited` is iOS 18+ and not present in the
            // macOS SDK this file also compiles against, so match it by rawValue
            // (4) rather than by symbol. Limited access still lets us add a new
            // contact, so it's usable.
            if status.rawValue == 4 { return .limited }
            return .denied
        }
    }
}
#endif
