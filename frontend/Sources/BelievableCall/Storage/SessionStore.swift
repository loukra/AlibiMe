import Foundation

/// Thread-safe holder for the current session token. `APIClient` reads from it
/// off the main actor, while the UI updates it on the main actor, so it is kept
/// deliberately small and lock-protected.
public final class TokenHolder: TokenProviding, @unchecked Sendable {
    private let lock = NSLock()
    private var token: String?

    public init(token: String? = nil) { self.token = token }

    public var sessionToken: String? {
        lock.lock(); defer { lock.unlock() }
        return token
    }

    public func update(_ token: String?) {
        lock.lock(); defer { lock.unlock() }
        self.token = token
    }
}

/// Persists the session across launches. Production uses the Keychain; tests and
/// previews use an in-memory store.
public protocol SessionStoring: AnyObject, Sendable {
    func load() -> Session?
    func save(_ session: Session)
    func clear()
}

/// In-memory session store for tests and SwiftUI previews.
public final class InMemorySessionStore: SessionStoring, @unchecked Sendable {
    private let lock = NSLock()
    private var session: Session?
    public init(session: Session? = nil) { self.session = session }
    public func load() -> Session? { lock.lock(); defer { lock.unlock() }; return session }
    public func save(_ session: Session) { lock.lock(); defer { lock.unlock() }; self.session = session }
    public func clear() { lock.lock(); defer { lock.unlock() }; session = nil }
}

#if canImport(Security)
import Security

/// Keychain-backed session storage. The opaque session token and minimal user
/// identity are stored as a single JSON blob under one keychain item.
public final class KeychainSessionStore: SessionStoring, @unchecked Sendable {
    private let service: String
    private let account = "session"

    public init(service: String = "com.believablecall.session") {
        self.service = service
    }

    private struct Stored: Codable {
        let token: String
        let userID: String
        let maskedNumber: String?
    }

    public func load() -> Session? {
        var query = baseQuery()
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data,
              let stored = try? JSONDecoder().decode(Stored.self, from: data) else {
            return nil
        }
        return Session(token: stored.token, userID: stored.userID, maskedNumber: stored.maskedNumber)
    }

    public func save(_ session: Session) {
        let stored = Stored(token: session.token, userID: session.userID, maskedNumber: session.maskedNumber)
        guard let data = try? JSONEncoder().encode(stored) else { return }
        clear()
        var query = baseQuery()
        query[kSecValueData as String] = data
        query[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        SecItemAdd(query as CFDictionary, nil)
    }

    public func clear() {
        SecItemDelete(baseQuery() as CFDictionary)
    }

    private func baseQuery() -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }
}
#endif
