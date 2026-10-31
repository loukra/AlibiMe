import Foundation
import Observation

/// Drives the Profile tab: loads the user's optional context profile + the
/// profile option catalogs, edits them, and saves. Everything is optional —
/// partial or empty is normal and never an error. The first name a caller may
/// say lives here too, picked from the server's list.
@MainActor
@Observable
public final class ProfileViewModel {
    public private(set) var phase: Phase = .idle
    public var profile = ContextProfile()
    public private(set) var options = ProfileOptions()
    public var errorMessage: String?
    public private(set) var didSave = false
    /// From the server's list only; set through `chooseFirstName`.
    public private(set) var firstName: String?
    /// Search results for the first-name picker.
    public private(set) var firstNameResults: [String] = []
    /// The profile as the server last had it, so the screen knows whether
    /// there is anything to save.
    private var saved = ContextProfile()

    public enum Phase: Equatable { case idle, loading, ready, saving, failure }

    private let service: ContextProfileServicing
    private let templates: TemplateServicing
    /// The account, which holds the first name.
    private let account: ProfileServicing
    public var onSessionExpired: (() -> Void)?

    public init(service: ContextProfileServicing, templates: TemplateServicing, account: ProfileServicing) {
        self.service = service
        self.templates = templates
        self.account = account
    }

    public var isSaving: Bool { phase == .saving }
    public var hasChanges: Bool { profile != saved }

    public func load() async {
        phase = .loading
        errorMessage = nil
        do {
            async let profileTask = service.get()
            async let optionsTask = templates.options()
            async let meTask = account.me()
            let (loaded, opts, me) = try await (profileTask, optionsTask, meTask)
            firstName = me.firstName
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

    /// Looks up names on the server's list. Empty input clears the results.
    public func searchFirstNames(_ query: String) async {
        let prefix = query.trimmingCharacters(in: .whitespaces)
        guard !prefix.isEmpty else {
            firstNameResults = []
            return
        }
        do {
            let names = try await account.firstNames(matching: prefix)
            guard !Task.isCancelled else { return }
            firstNameResults = names
        } catch {
            // A newer search replaced this one; its result doesn't matter.
            if !Task.isCancelled { show(error) }
        }
    }

    /// Picks a name from the list, or removes it with nil.
    public func chooseFirstName(_ name: String?) async {
        errorMessage = nil
        didSave = false
        do {
            firstName = try await account.setFirstName(name).firstName
            didSave = true
        } catch {
            show(error)
        }
    }

    private func handle(_ error: Error) {
        show(error)
        phase = .failure
    }

    /// The message alone, for errors that leave the profile itself usable.
    private func show(_ error: Error) {
        let apiError = asAPIError(error)
        if apiError.requiresReauth { onSessionExpired?(); return }
        errorMessage = ErrorCopy.userMessage(for: apiError)
    }
}
