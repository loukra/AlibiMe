import Foundation
import Observation

/// Top-level app state machine. Keeps the small set of phases from the spec and
/// owns session lifecycle (restore / sign-in / sign-out / expiry) so individual
/// screens never invent their own interpretation of auth state.
@MainActor
@Observable
public final class AppModel {
    public enum Phase: Equatable {
        case launching
        case unauthenticated
        case authenticated
    }

    public private(set) var phase: Phase = .launching
    public private(set) var session: Session?
    /// Set when a session expired mid-use, so the auth screen can explain why.
    public private(set) var sessionExpiredNotice = false

    public let env: AppEnvironment

    public init(env: AppEnvironment) {
        self.env = env
    }

    /// Launch: restore a persisted session if present. The backend remains the
    /// source of truth; an expired token is discovered on first authed call and
    /// routed through `handleSessionExpired`.
    public func restore() {
        if let stored = env.sessionStore.load() {
            session = stored
            env.tokenHolder.update(stored.token)
            phase = .authenticated
        } else {
            phase = .unauthenticated
        }
    }

    public func signIn(_ session: Session) {
        self.session = session
        env.sessionStore.save(session)
        env.tokenHolder.update(session.token)
        sessionExpiredNotice = false
        phase = .authenticated
        registerDeviceInBackground()
    }

    public func signOut() {
        clearSession()
        sessionExpiredNotice = false
        phase = .unauthenticated
    }

    public func handleSessionExpired() {
        clearSession()
        sessionExpiredNotice = true
        phase = .unauthenticated
    }

    private func clearSession() {
        session = nil
        env.sessionStore.clear()
        env.tokenHolder.update(nil)
    }

    private func registerDeviceInBackground() {
        let devices = env.devices
        let deviceID = env.prefs.deviceID
        Task { try? await devices.register(deviceID: deviceID, pushToken: nil, appVersion: nil, osVersion: nil) }
    }

    // MARK: View-model factories (wire session-expiry routing once)

    public func makeAuthViewModel() -> AuthViewModel {
        let vm = AuthViewModel(auth: env.auth, deviceID: env.prefs.deviceID)
        vm.onAuthenticated = { [weak self] session in self?.signIn(session) }
        return vm
    }

    public func makeHomeViewModel() -> HomeViewModel {
        let vm = HomeViewModel(templateService: env.templates,
                               requestService: env.requests,
                               profileService: env.profile,
                               prefs: env.prefs)
        vm.onSessionExpired = { [weak self] in self?.handleSessionExpired() }
        return vm
    }

    public func makeHistoryViewModel() -> HistoryViewModel {
        let vm = HistoryViewModel(service: env.history)
        vm.onSessionExpired = { [weak self] in self?.handleSessionExpired() }
        return vm
    }

    public func makeSettingsViewModel() -> SettingsViewModel {
        let vm = SettingsViewModel(profileService: env.profile, auth: env.auth)
        vm.onSignOut = { [weak self] in self?.signOut() }
        vm.onSessionExpired = { [weak self] in self?.handleSessionExpired() }
        return vm
    }
}
