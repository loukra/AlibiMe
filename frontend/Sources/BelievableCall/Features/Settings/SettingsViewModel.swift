import Foundation
import Observation

/// Settings: verified-number snapshot, profile fields, credits, and sign out.
@MainActor
@Observable
public final class SettingsViewModel {
    public private(set) var profile: UserProfile?
    public var locale: String = "en"
    /// From the server's list only; set through `chooseFirstName`.
    public private(set) var firstName: String?
    /// Search results for the first-name picker.
    public private(set) var firstNameResults: [String] = []
    public var timezone: String = "UTC"
    public private(set) var isLoading = false
    public private(set) var isSaving = false
    public var errorMessage: String?
    public private(set) var didSave = false
    /// Lightweight success note shown in the credits section after a top-up.
    public private(set) var creditSuccessMessage: String?

    /// Templates to pick the Action Button's quick alibi from.
    public private(set) var quickAlibiTemplates: [TemplateSummary] = []
    public private(set) var quickAlibi: QuickAlibi?

    private let profileService: ProfileServicing
    private let auth: AuthServicing
    private let creditPackages: CreditPackagesServicing
    private let templates: TemplateServicing?
    private let prefs: PreferencesStoring
    private let purchases: PurchaseServicing
    private let accountToken: UUID?
    /// The support and privacy pages, served by the backend (`/support`,
    /// `/privacy`), so they live on the API domain.
    public let supportURL: URL
    public let privacyURL: URL
    public var onSignOut: (() -> Void)?
    public var onSessionExpired: (() -> Void)?

    public init(profileService: ProfileServicing,
                auth: AuthServicing,
                creditPackages: CreditPackagesServicing,
                templates: TemplateServicing? = nil,
                prefs: PreferencesStoring = InMemoryPreferences(),
                purchases: PurchaseServicing = MockPurchaseService(),
                accountToken: UUID? = nil,
                backendURL: URL = URL(string: "http://127.0.0.1:8000")!) {
        self.profileService = profileService
        self.auth = auth
        self.creditPackages = creditPackages
        self.templates = templates
        self.prefs = prefs
        self.purchases = purchases
        self.accountToken = accountToken
        self.supportURL = Self.page("support", on: backendURL)
        self.privacyURL = Self.page("privacy", on: backendURL)
        self.quickAlibi = prefs.quickAlibi
    }

    /// A fresh view model for the Add Credits bottom sheet, wired to the same
    /// session-expiry handling as the rest of Settings.
    public func makeCreditPackagesViewModel() -> CreditPackagesViewModel {
        let vm = CreditPackagesViewModel(service: creditPackages, purchases: purchases,
                                         accountToken: accountToken)
        vm.onSessionExpired = { [weak self] in self?.onSessionExpired?() }
        return vm
    }

    /// Called after the sheet grants credits: refresh the authoritative balance
    /// from the backend and surface a brief success note.
    public func didAcquireCredits(_ result: CreditAcquisition) async {
        creditSuccessMessage = String(localized: "\(result.grantedCredits) credits added")
        await load()
    }

    public var maskedNumber: String? { profile?.phone.maskedNumber }
    public var creditsAvailable: Int { profile?.entitlements.creditsAvailable ?? 0 }
    public var appVersion: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
    }

    public func load() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let profile = try await profileService.me()
            apply(profile)
            if let templates {
                quickAlibiTemplates = try await templates.list()
            }
        } catch {
            handle(error)
        }
    }

    // MARK: Quick alibi (Action Button)

    /// Channels the chosen template can send on, call first.
    public var quickAlibiChannels: [Channel] {
        guard let id = quickAlibi?.templateID,
              let template = quickAlibiTemplates.first(where: { $0.id == id }) else { return [] }
        return Channel.allCases.filter(template.supports)
    }

    /// Pick the template; nil turns the quick alibi off.
    public func setQuickAlibi(templateID: String?) {
        guard let templateID,
              let template = quickAlibiTemplates.first(where: { $0.id == templateID }) else {
            storeQuickAlibi(nil)
            return
        }
        let current = quickAlibi?.channel ?? .call
        let channel = template.supports(current) ? current : (Channel.allCases.first(where: template.supports) ?? .call)
        storeQuickAlibi(QuickAlibi(templateID: template.id, templateName: template.displayName,
                                   channel: channel, delaySeconds: quickAlibi?.delaySeconds ?? 0))
    }

    public func setQuickAlibiChannel(_ channel: Channel) {
        guard var alibi = quickAlibi, quickAlibiChannels.contains(channel) else { return }
        alibi.channel = channel
        storeQuickAlibi(alibi)
    }

    public func setQuickAlibiDelay(_ seconds: Int) {
        guard var alibi = quickAlibi else { return }
        alibi.delaySeconds = seconds
        storeQuickAlibi(alibi)
    }

    private func storeQuickAlibi(_ alibi: QuickAlibi?) {
        quickAlibi = alibi
        prefs.quickAlibi = alibi
    }

    private func apply(_ profile: UserProfile) {
        self.profile = profile
        locale = profile.locale
        timezone = profile.timezone
        firstName = profile.firstName
    }

    /// Looks up names on the server's list. Empty input clears the results.
    public func searchFirstNames(_ query: String) async {
        let prefix = query.trimmingCharacters(in: .whitespaces)
        guard !prefix.isEmpty else {
            firstNameResults = []
            return
        }
        do {
            let names = try await profileService.firstNames(matching: prefix)
            guard !Task.isCancelled else { return }
            firstNameResults = names
        } catch {
            // A newer search replaced this one; its result doesn't matter.
            if !Task.isCancelled { handle(error) }
        }
    }

    /// Picks a name from the list, or removes it with nil.
    public func chooseFirstName(_ name: String?) async {
        errorMessage = nil
        didSave = false
        do {
            let updated = try await profileService.setFirstName(name)
            profile = updated
            firstName = updated.firstName
            didSave = true
        } catch {
            handle(error)
        }
    }

    /// Whether the language differs from what the server has.
    public var hasChanges: Bool {
        guard let profile else { return false }
        return locale != profile.locale
    }

    /// Settings save as they change.
    public func saveIfChanged() async {
        guard hasChanges, !isSaving else { return }
        await save()
    }

    public func save() async {
        isSaving = true
        errorMessage = nil
        didSave = false
        let sentLocale = locale
        do {
            let updated = try await profileService.update(locale: sentLocale, timezone: timezone)
            // Keep what the user changed while this save was on its way.
            if locale == sentLocale {
                apply(updated)
            } else {
                profile = updated
            }
            didSave = true
            isSaving = false
            if hasChanges { await save() }
        } catch {
            isSaving = false
            handle(error)
        }
    }

    public private(set) var isDeleting = false

    /// Deletes the account for good, then signs out. Local picks that point at
    /// the old account (the quick alibi) are cleared too.
    public func deleteAccount() async {
        isDeleting = true
        errorMessage = nil
        defer { isDeleting = false }
        do {
            try await profileService.deleteAccount()
            storeQuickAlibi(nil)
            prefs.selectedTemplateID = nil
            onSignOut?()
        } catch {
            handle(error)
        }
    }

    public func signOut() async {
        // Best-effort server logout; the session is cleared locally regardless.
        try? await auth.logout()
        onSignOut?()
    }

    private func handle(_ error: Error) {
        let apiError = asAPIError(error)
        if apiError.requiresReauth { onSessionExpired?(); return }
        errorMessage = ErrorCopy.userMessage(for: apiError)
    }
}

extension SettingsViewModel {
    /// A public page on the server, in the app's language (German or English).
    static func page(_ name: String, on backendURL: URL) -> URL {
        var parts = URLComponents(url: backendURL.appendingPathComponent(name), resolvingAgainstBaseURL: false)
        parts?.queryItems = [URLQueryItem(name: "lang", value: AppLanguage.current)]
        return parts?.url ?? backendURL.appendingPathComponent(name)
    }
}
