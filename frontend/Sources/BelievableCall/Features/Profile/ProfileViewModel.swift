import Foundation
import Observation

/// Drives the Profile tab: loads the user's optional context profile + the
/// profile option catalogs, edits them, and saves. Everything is optional —
/// partial or empty is normal and never an error.
@MainActor
@Observable
public final class ProfileViewModel {
    public private(set) var phase: Phase = .idle
    public var profile = ContextProfile()
    public private(set) var options = ProfileOptions()
    public var errorMessage: String?
    public private(set) var didSave = false

    public enum Phase: Equatable { case idle, loading, ready, saving, failure }

    private let service: ContextProfileServicing
    private let templates: TemplateServicing
    public var onSessionExpired: (() -> Void)?

    public init(service: ContextProfileServicing, templates: TemplateServicing) {
        self.service = service
        self.templates = templates
    }

    public var isSaving: Bool { phase == .saving }

    public func load() async {
        phase = .loading
        errorMessage = nil
        do {
            async let profileTask = service.get()
            async let optionsTask = templates.options()
            let (loaded, opts) = try await (profileTask, optionsTask)
            profile = loaded
            options = opts.profile
            phase = .ready
        } catch {
            handle(error)
        }
    }

    public func save() async {
        phase = .saving
        errorMessage = nil
        didSave = false
        do {
            profile = try await service.update(profile)
            didSave = true
            phase = .ready
        } catch {
            handle(error)
        }
    }

    /// Clear everything back to empty (and persist the cleared state).
    public func clearAll() async {
        profile = ContextProfile()
        await save()
    }

    private func handle(_ error: Error) {
        let apiError = asAPIError(error)
        if apiError.requiresReauth { onSessionExpired?(); phase = .failure; return }
        errorMessage = ErrorCopy.userMessage(for: apiError)
        phase = .failure
    }
}
