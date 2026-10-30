import Foundation
import Observation

/// The Templates library: built-in templates plus the user's own custom ones,
/// with create/delete. Reuses the same `TemplateServicing` as the rest of the app.
@MainActor
@Observable
public final class TemplatesViewModel {
    public private(set) var templates: [TemplateSummary] = []
    public private(set) var isLoading = false
    public var errorMessage: String?
    /// Whether the user has any context profile set (drives the optional note).
    public private(set) var hasProfileContext = false

    private let service: TemplateServicing
    private let contextProfile: ContextProfileServicing?
    public var onSessionExpired: (() -> Void)?

    public init(service: TemplateServicing, contextProfile: ContextProfileServicing? = nil) {
        self.service = service
        self.contextProfile = contextProfile
    }

    public var systemTemplates: [TemplateSummary] { templates.filter { !$0.isCustom } }
    public var customTemplates: [TemplateSummary] { templates.filter { $0.isCustom } }
    /// The built-in templates by category, in the picker's order.
    public var systemTemplatesByCategory: [(category: TemplateCategory, templates: [TemplateSummary])] {
        Dictionary(grouping: systemTemplates, by: \.category)
            .map { ($0.key, $0.value.sorted { $0.displayName < $1.displayName }) }
            .sorted { $0.category.sortOrder < $1.category.sortOrder }
    }

    /// Show the "configure your profile" note only when we know there's no context.
    public var showProfileNote: Bool { contextProfile != nil && !hasProfileContext }

    public func load() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            templates = try await service.list()
            if let contextProfile {
                hasProfileContext = (try? await contextProfile.get())?.hasAnyContext ?? false
            }
        } catch {
            handle(error)
        }
    }

    public func delete(_ template: TemplateSummary) async {
        guard template.isCustom else { return }
        do {
            try await service.delete(id: template.id)
            templates.removeAll { $0.id == template.id }
        } catch {
            handle(error)
        }
    }

    public func makeEditorViewModel() -> CustomTemplateEditorViewModel {
        let vm = CustomTemplateEditorViewModel(service: service)
        vm.onSessionExpired = { [weak self] in self?.onSessionExpired?() }
        return vm
    }

    private func handle(_ error: Error) {
        let apiError = asAPIError(error)
        if apiError.requiresReauth { onSessionExpired?(); return }
        errorMessage = ErrorCopy.userMessage(for: apiError)
    }
}

/// Drives the structured custom-template editor. The user only makes safe,
/// backend-validated choices — never free-form prompt/SMS text.
@MainActor
@Observable
public final class CustomTemplateEditorViewModel: Identifiable {
    public enum Phase: Equatable { case idle, loadingOptions, ready, submitting, failure }

    public private(set) var phase: Phase = .idle
    public private(set) var options: TemplateOptions?
    public var draft = CustomTemplateDraft()
    public var errorMessage: String?

    private let service: TemplateServicing
    public var onSessionExpired: (() -> Void)?

    public init(service: TemplateServicing) {
        self.service = service
    }

    public var isSubmitting: Bool { phase == .submitting }

    public var canSubmit: Bool {
        !draft.displayName.trimmingCharacters(in: .whitespaces).isEmpty
            && !draft.persona.isEmpty
            && !draft.reason.isEmpty
            && !draft.channels.isEmpty
            && phase != .submitting
    }

    public func load() async {
        phase = .loadingOptions
        errorMessage = nil
        do {
            let opts = try await service.options()
            options = opts
            // Sensible defaults from the backend catalog.
            if draft.persona.isEmpty { draft.persona = opts.personas.first?.code ?? "" }
            if draft.reason.isEmpty { draft.reason = opts.reasons.first?.code ?? "" }
            if !opts.categories.contains(draft.category) {
                draft.category = opts.categories.first ?? draft.category
            }
            draft.callMaxSeconds = opts.callSecondsDefault
            phase = .ready
        } catch {
            handle(error)
        }
    }

    public func toggle(_ channel: Channel, on: Bool) {
        if on { draft.channels.insert(channel) } else { draft.channels.remove(channel) }
    }

    @discardableResult
    public func submit() async -> TemplateSummary? {
        guard canSubmit else { return nil }
        phase = .submitting
        errorMessage = nil
        do {
            let created = try await service.createCustom(draft)
            phase = .ready
            return created
        } catch {
            handle(error)
            return nil
        }
    }

    private func handle(_ error: Error) {
        let apiError = asAPIError(error)
        if apiError.requiresReauth { onSessionExpired?(); phase = .failure; return }
        errorMessage = ErrorCopy.userMessage(for: apiError)
        phase = .failure
    }
}
