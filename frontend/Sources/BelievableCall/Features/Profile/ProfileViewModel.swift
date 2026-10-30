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
    /// The profile as the server last had it, so the screen knows whether
    /// there is anything to save.
    private var saved = ContextProfile()

    public enum Phase: Equatable { case idle, loading, ready, saving, failure }

    private let service: ContextProfileServicing
    private let templates: TemplateServicing
    public var onSessionExpired: (() -> Void)?

    public init(service: ContextProfileServicing, templates: TemplateServicing) {
        self.service = service
        self.templates = templates
    }

    public var isSaving: Bool { phase == .saving }
    public var hasChanges: Bool { profile != saved }

    public func load() async {
        phase = .loading
        errorMessage = nil
        do {
            async let profileTask = service.get()
            async let optionsTask = templates.options()
            let (loaded, opts) = try await (profileTask, optionsTask)
            profile = loaded
            saved = loaded
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
        // The screen saves after every answer, so another answer can come in
        // while this one is on its way: keep it rather than overwrite it with
        // the server's reply to the older state.
        let sent = profile
        do {
            let stored = try await service.update(sent)
            saved = stored
            if profile == sent { profile = stored }
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
