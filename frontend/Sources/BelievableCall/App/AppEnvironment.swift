import Foundation

/// Lightweight dependency container. Owns the single `APIClient` and the live
/// services, plus storage. Injected into view models; swapped for mocks in
/// previews and tests.
public final class AppEnvironment: @unchecked Sendable {
    public let baseURL: URL
    public let tokenHolder: TokenHolder
    public let apiClient: APIClient
    public let sessionStore: SessionStoring
    public let prefs: PreferencesStoring
    public let contactLinks: ContactLinkStoring

    public let auth: AuthServicing
    public let templates: TemplateServicing
    public let requests: RequestServicing
    public let history: HistoryServicing
    public let profile: ProfileServicing
    public let devices: DeviceServicing
    public let contacts: ContactsServicing
    public let creditPackages: CreditPackagesServicing

    public init(baseURL: URL,
                transport: HTTPTransport = URLSession.shared,
                sessionStore: SessionStoring,
                prefs: PreferencesStoring,
                contactLinks: ContactLinkStoring? = nil,
                contacts: ContactsServicing? = nil) {
        self.baseURL = baseURL
        self.sessionStore = sessionStore
        self.prefs = prefs
        self.contactLinks = contactLinks ?? Self.defaultContactLinkStore()
        let holder = TokenHolder()
        self.tokenHolder = holder
        let client = APIClient(baseURL: baseURL, transport: transport, tokenProvider: holder)
        self.apiClient = client
        self.auth = LiveAuthService(client: client)
        self.templates = LiveTemplateService(client: client)
        self.requests = LiveRequestService(client: client)
        self.history = LiveHistoryService(client: client)
        self.profile = LiveProfileService(client: client)
        self.devices = LiveDeviceService(client: client)
        self.contacts = contacts ?? Self.defaultContactsService()
        self.creditPackages = LiveCreditPackagesService(client: client)
    }

    private static func defaultContactLinkStore() -> ContactLinkStoring {
        UserDefaultsContactLinkStore()
    }

    private static func defaultContactsService() -> ContactsServicing {
        #if canImport(Contacts)
        return LiveContactsService()
        #else
        return MockContactsService(status: .denied)
        #endif
    }

    /// Convenience for the default local backend. Override the URL for device
    /// builds pointed at a deployed backend.
    public static func live(baseURL: URL = URL(string: "http://127.0.0.1:8000")!) -> AppEnvironment {
        #if canImport(Security)
        let store: SessionStoring = KeychainSessionStore()
        #else
        let store: SessionStoring = InMemorySessionStore()
        #endif
        return AppEnvironment(baseURL: baseURL, sessionStore: store, prefs: UserDefaultsPreferences())
    }
}
