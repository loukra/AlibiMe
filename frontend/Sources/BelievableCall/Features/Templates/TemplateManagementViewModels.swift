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

    /// Reload after the editor saved, reset or deleted a template.
    public func editorFinished() async { await load() }

    /// `editing` nil: a new template. Otherwise the tapped one, own or built-in.
    public func makeEditorViewModel(editing: TemplateSummary? = nil) -> CustomTemplateEditorViewModel {
        let vm = CustomTemplateEditorViewModel(service: service, editing: editing)
        vm.onSessionExpired = { [weak self] in self?.onSessionExpired?() }
        return vm
    }

    private func handle(_ error: Error) {
        let apiError = asAPIError(error)
        if apiError.requiresReauth { onSessionExpired?(); return }
        errorMessage = ErrorCopy.userMessage(for: apiError)
    }
}

/// Drives the template editor: three tile steps (who, why, how urgent), then an
/// overview with the name, channels and the rarer choices. Editing an existing
/// template opens on the overview. The user only makes safe, backend-validated
/// choices — never free-form prompt/SMS text.
@MainActor
@Observable
public final class CustomTemplateEditorViewModel: Identifiable {
    public enum Phase: Equatable { case idle, loadingOptions, ready, submitting, failure }
    public enum Step: Int, CaseIterable { case who, why, urgency, overview }

    public private(set) var phase: Phase = .idle
    public private(set) var options: TemplateOptions?
    public var draft = CustomTemplateDraft()
    public var errorMessage: String?
    public private(set) var step: Step
    /// The template being edited; nil while creating a new one.
    public let editing: TemplateSummary?
    /// Once the overview was shown, a changed answer returns straight to it.
    private var reachedOverview: Bool

    private let service: TemplateServicing
    public var onSessionExpired: (() -> Void)?

    public init(service: TemplateServicing, editing: TemplateSummary? = nil) {
        self.service = service
        self.editing = editing
        self.step = editing == nil ? .who : .overview
        self.reachedOverview = editing != nil
        if let editing {
            draft = editing.choices ?? CustomTemplateDraft()
            if editing.choices == nil { draft.displayName = editing.displayName }
        }
    }

    public var isSubmitting: Bool { phase == .submitting }
    public var isEditing: Bool { editing != nil }
    /// An edited built-in can go back to the original.
    public var canReset: Bool { editing?.isEdited == true }
    public var canDelete: Bool { editing?.isCustom == true }

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
            if !opts.categories.contains(draft.category) {
                draft.category = opts.categories.first ?? draft.category
            }
            if !isEditing { draft.callMaxSeconds = opts.callSecondsDefault }
            phase = .ready
        } catch {
            handle(error)
        }
    }

    // MARK: Steps

    public func go(to step: Step) { self.step = step }

    /// On a step opened from the overview, Back returns to it; on the first
    /// pass it goes one step back. The first step offers Cancel instead.
    public var canGoBack: Bool {
        step != .overview && (reachedOverview || step != .who)
    }

    public func back() {
        if reachedOverview {
            step = .overview
        } else if let previous = Step(rawValue: step.rawValue - 1) {
            step = previous
        }
    }

    public func choosePersona(_ code: String) {
        draft.persona = code
        advance(from: .who)
    }

    public func chooseReason(_ code: String) {
        draft.reason = code
        if let category = Self.category(forReason: code) { draft.category = category }
        advance(from: .why)
    }

    public func chooseUrgency(_ code: String) {
        draft.urgency = code
        advance(from: .urgency)
    }

    private func advance(from current: Step) {
        let next: Step = reachedOverview ? .overview : Step(rawValue: current.rawValue + 1) ?? .overview
        if next == .overview && !reachedOverview {
            reachedOverview = true
            if draft.displayName.trimmingCharacters(in: .whitespaces).isEmpty {
                draft.displayName = suggestedName
            }
        }
        step = next
    }

    public func toggle(_ channel: Channel, on: Bool) {
        if on { draft.channels.insert(channel) } else { draft.channels.remove(channel) }
    }

    // MARK: Labels

    public func personaLabel(_ code: String) -> String {
        Self.tileLabel(options?.personas.first { $0.code == code }?.label ?? code)
    }

    public func reasonLabel(_ code: String) -> String {
        Self.capitalizedFirst(options?.reasons.first { $0.code == code }?.label ?? code)
    }

    /// "your manager", as the catalog phrases it.
    public var personaPhrase: String {
        options?.personas.first { $0.code == draft.persona }?.label ?? draft.persona
    }

    /// "Your manager calls about a travel assignment."
    public var summary: String {
        guard !draft.persona.isEmpty, !draft.reason.isEmpty else { return "" }
        let who = personaPhrase
        let why = options?.reasons.first { $0.code == draft.reason }?.label ?? draft.reason
        let verb = draft.channels == [.text] ? "texts" : "calls"
        return "\(Self.capitalizedFirst(who)) \(verb) about \(why)."
    }

    private var suggestedName: String {
        String("\(personaLabel(draft.persona)): \(reasonLabel(draft.reason).lowercased())".prefix(120))
    }

    /// Personas grouped for the tiles, the group of the current reason first.
    public var personaGroups: [(title: String, options: [TemplateOption])] {
        Self.grouped(options?.personas ?? [], by: Self.group(forPersona:))
    }

    /// Reasons grouped, the persona's own group first.
    public var reasonGroups: [(title: String, options: [TemplateOption])] {
        let groups = Self.grouped(options?.reasons ?? [], by: Self.group(forReason:))
        let first = Self.group(forPersona: draft.persona)
        return groups.filter { $0.title == first } + groups.filter { $0.title != first }
    }

    // MARK: Save, reset, delete

    @discardableResult
    public func submit() async -> TemplateSummary? {
        guard canSubmit else { return nil }
        phase = .submitting
        errorMessage = nil
        // The card's description is the scenario in one sentence, so it never
        // describes an answer the user since changed.
        if !summary.isEmpty { draft.description = summary }
        do {
            let saved: TemplateSummary
            if let editing {
                saved = try await service.update(id: editing.id, draft)
            } else {
                saved = try await service.createCustom(draft)
            }
            phase = .ready
            return saved
        } catch {
            handle(error)
            return nil
        }
    }

    /// Reset an edited built-in, or delete an own template. Both remove the
    /// user's template; for a built-in the original shows again.
    public func remove() async -> Bool {
        guard let editing, canReset || canDelete else { return false }
        phase = .submitting
        errorMessage = nil
        do {
            try await service.delete(id: editing.id)
            phase = .ready
            return true
        } catch {
            handle(error)
            return false
        }
    }

    private func handle(_ error: Error) {
        let apiError = asAPIError(error)
        if apiError.requiresReauth { onSessionExpired?(); phase = .failure; return }
        errorMessage = ErrorCopy.userMessage(for: apiError)
        phase = .failure
    }
}

extension CustomTemplateEditorViewModel {
    /// Group titles, in tile order. Reason codes start with their group.
    static let groupOrder = ["Work", "Home", "Family", "Friends", "Partner", "Life changes", "Safety"]

    static func group(forReason code: String) -> String {
        switch code.split(separator: "_").first {
        case "work": return "Work"
        case "home": return "Home"
        case "family": return "Family"
        case "social": return "Friends"
        case "privacy": return "Partner"
        case "transition": return "Life changes"
        default: return "Safety"
        }
    }

    static func group(forPersona code: String) -> String {
        switch code {
        case "manager", "team_lead", "coworker", "hr_office_contact", "client", "office_line":
            return "Work"
        case "roommate", "landlord_building_contact", "neighbor", "repair_service_contact",
             "delivery_service_contact":
            return "Home"
        case "sibling", "parent", "family_member", "childcare_contact", "eldercare_contact",
             "family_friend":
            return "Family"
        case "partner", "spouse", "romantic_contact":
            return "Partner"
        case "trusted_friend", "pickup_contact":
            return "Safety"
        default:
            return "Friends"
        }
    }

    /// The editor's category follows the reason, so it is never asked.
    static func category(forReason code: String) -> String? {
        switch group(forReason: code) {
        case "Work": return "work"
        case "Home": return "home_logistics"
        case "Family": return "family_care"
        case "Friends": return "social_exit"
        case "Partner": return "relationship_privacy"
        case "Life changes": return "travel_transition"
        default: return "safety_discomfort"
        }
    }

    static func grouped(_ options: [TemplateOption],
                        by group: (String) -> String) -> [(title: String, options: [TemplateOption])] {
        let byGroup = Dictionary(grouping: options) { group($0.code) }
        return groupOrder.compactMap { title in
            byGroup[title].map { (title, $0) }
        }
    }

    /// "your manager" → "Manager", "someone you're seeing" → "Someone you're seeing".
    static func tileLabel(_ label: String) -> String {
        var text = label
        for article in ["your ", "the ", "a "] where text.hasPrefix(article) {
            text = String(text.dropFirst(article.count))
            break
        }
        return capitalizedFirst(text)
    }

    static func capitalizedFirst(_ text: String) -> String {
        text.prefix(1).uppercased() + text.dropFirst()
    }

    static func humanized(_ code: String) -> String {
        capitalizedFirst(code.replacingOccurrences(of: "_", with: " "))
    }
}
