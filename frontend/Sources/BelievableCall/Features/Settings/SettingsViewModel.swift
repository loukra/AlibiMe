import Foundation
import Observation

/// Settings: verified-number snapshot, profile fields, credits, and sign out.
@MainActor
@Observable
public final class SettingsViewModel {
    public private(set) var profile: UserProfile?
    public var displayName: String = ""
    public var locale: String = "en"
    public var timezone: String = "UTC"
    public private(set) var isLoading = false
    public private(set) var isSaving = false
    public var errorMessage: String?
    public private(set) var didSave = false
    /// Lightweight success note shown in the credits section after a top-up.
    public private(set) var creditSuccessMessage: String?

    private let profileService: ProfileServicing
    private let auth: AuthServicing
    private let creditPackages: CreditPackagesServicing
    public var onSignOut: (() -> Void)?
    public var onSessionExpired: (() -> Void)?

    public init(profileService: ProfileServicing,
                auth: AuthServicing,
                creditPackages: CreditPackagesServicing) {
        self.profileService = profileService
        self.auth = auth
        self.creditPackages = creditPackages
    }

    /// A fresh view model for the Add Credits bottom sheet, wired to the same
    /// session-expiry handling as the rest of Settings.
    public func makeCreditPackagesViewModel() -> CreditPackagesViewModel {
        let vm = CreditPackagesViewModel(service: creditPackages)
        vm.onSessionExpired = { [weak self] in self?.onSessionExpired?() }
        return vm
    }

    /// Called after the sheet grants credits: refresh the authoritative balance
    /// from the backend and surface a brief success note.
    public func didAcquireCredits(_ result: CreditAcquisition) async {
        creditSuccessMessage = "\(result.grantedCredits) credits added"
        await load()
    }

    public var maskedNumber: String? { profile?.phone.maskedNumber }
    public var creditsAvailable: Int { profile?.entitlements.creditsAvailable ?? 0 }
    public var planLabel: String { profile?.entitlements.planLabel ?? "—" }
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
        } catch {
            handle(error)
        }
    }

    private func apply(_ profile: UserProfile) {
        self.profile = profile
        displayName = profile.displayName ?? ""
        locale = profile.locale
        timezone = profile.timezone
    }

    public func save() async {
        isSaving = true
        errorMessage = nil
        didSave = false
        defer { isSaving = false }
        do {
            let trimmedName = displayName.trimmingCharacters(in: .whitespaces)
            let updated = try await profileService.update(
                locale: locale,
                timezone: timezone,
                displayName: trimmedName.isEmpty ? nil : trimmedName
            )
            apply(updated)
            didSave = true
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
