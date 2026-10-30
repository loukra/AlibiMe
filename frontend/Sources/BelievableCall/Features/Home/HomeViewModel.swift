import Foundation
import Observation

/// The action-first home surface. Owns the template/channel/timing selection
/// and the create-request fast path, plus the active-request state.
@MainActor
@Observable
public final class HomeViewModel {
    public private(set) var templates: [TemplateSummary] = []
    public private(set) var selectedTemplate: TemplateSummary?
    public var channel: Channel = .call
    public var timing: TimingOption = .now
    public private(set) var profile: UserProfile?
    public private(set) var activeRequest: RequestSummary?

    public private(set) var isLoading = false
    public private(set) var isSubmitting = false
    public var errorMessage: String?

    /// Bumps each time a job is successfully created; the channel of that job is
    /// in `lastCreatedChannel`. Drives the "fly to History" animation.
    public private(set) var createdJobCount = 0
    public private(set) var lastCreatedChannel: Channel = .call

    private let templateService: TemplateServicing
    private let requestService: RequestServicing
    private let profileService: ProfileServicing
    private let prefs: PreferencesStoring
    private let contacts: ContactsServicing
    private let contactLinks: ContactLinkStoring
    public var onSessionExpired: (() -> Void)?

    // MARK: Save Contact flow (after a call or text is set up, fully optional)

    /// The soft "Save this sender as a contact?" prompt. Non-blocking; set after
    /// a successful send when the binding hasn't been acted on before.
    public var pendingSenderPrompt: SenderIdentity?
    /// When set, the view presents the prefilled iOS new-contact sheet.
    public var contactSheetSender: SenderIdentity?
    /// When set, the view shows the "Contacts access is optional" notice.
    public var contactPermissionDeniedSender: SenderIdentity?

    public init(templateService: TemplateServicing,
                requestService: RequestServicing,
                profileService: ProfileServicing,
                prefs: PreferencesStoring,
                contacts: ContactsServicing,
                contactLinks: ContactLinkStoring) {
        self.templateService = templateService
        self.requestService = requestService
        self.profileService = profileService
        self.prefs = prefs
        self.contacts = contacts
        self.contactLinks = contactLinks
        if let saved = prefs.lastChannel, let ch = Channel(rawValue: saved) { channel = ch }
        if let delay = prefs.lastTimingDelay {
            timing = TimingOption.presets.first { $0.delaySeconds == delay } ?? .now
        }
    }

    // MARK: Derived UI state

    /// Channels supported by the selected template, in display order.
    public var availableChannels: [Channel] {
        guard let selectedTemplate else { return [] }
        return Channel.allCases.filter { selectedTemplate.supports($0) }
    }

    public var creditsAvailable: Int { profile?.entitlements.creditsAvailable ?? 0 }
    public var hasCredits: Bool { creditsAvailable > 0 }
    public var maskedNumber: String? { profile?.phone.maskedNumber }

    /// When a live request exists the home screen switches to a status-first
    /// state rather than offering a second parallel request.
    public var hasActiveRequest: Bool { activeRequest?.status.isLive == true }

    /// CTA copy that adapts to channel + timing, e.g. "Call me now",
    /// "Text me in 30 seconds", "Schedule call".
    public var primaryCTATitle: String {
        let verb = channel == .call ? "Call" : "Text"
        switch timing {
        case .now: return "\(verb) me now"
        case .in30Seconds: return "\(verb) me in 30 seconds"
        case .in5Minutes: return "\(verb) me in 5 minutes"
        case .schedule: return "Schedule \(channel == .call ? "call" : "text")"
        }
    }

    public var canSend: Bool {
        // Multiple jobs may be queued (up to the backend cap), so an existing
        // pending job no longer blocks sending — the backend enforces the cap
        // and surfaces an error if it's exceeded.
        !isSubmitting && selectedTemplate != nil && hasCredits
            && (profile?.phone.isVerified ?? false)
    }

    // MARK: Loading

    public func load() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            async let profileTask = profileService.me()
            async let templatesTask = templateService.list()
            let (loadedProfile, loadedTemplates) = try await (profileTask, templatesTask)
            profile = loadedProfile
            templates = loadedTemplates
            activeRequest = loadedProfile.activeRequest
            restoreSelection()
        } catch {
            handle(error)
        }
    }

    /// On foreground/resume (and each time the Home tab becomes visible), refresh
    /// the active request, profile, and the template catalog — so templates
    /// created on the Templates tab appear here too. The current selection is
    /// preserved if it still exists.
    public func refresh() async {
        if let updated = try? await profileService.me() {
            profile = updated
            // The chip always reflects the backend's soonest live job.
            activeRequest = updated.activeRequest
        }
        if let latest = try? await templateService.list() {
            templates = latest
            if let current = selectedTemplate, latest.contains(where: { $0.id == current.id }) {
                selectedTemplate = latest.first { $0.id == current.id }
            } else {
                restoreSelection()
            }
            reconcileChannel()
        }
    }

    private func restoreSelection() {
        let saved = prefs.selectedTemplateID
        selectedTemplate = templates.first { $0.id == saved } ?? templates.first
        reconcileChannel()
    }

    // MARK: Selection

    public func selectTemplate(_ template: TemplateSummary) {
        selectedTemplate = template
        prefs.selectedTemplateID = template.id
        reconcileChannel()
    }

    public func selectChannel(_ channel: Channel) {
        guard selectedTemplate?.supports(channel) ?? false else { return }
        self.channel = channel
        prefs.lastChannel = channel.rawValue
    }

    public func selectTiming(_ timing: TimingOption) {
        self.timing = timing
        prefs.lastTimingDelay = timing.delaySeconds
    }

    /// If the current channel isn't supported by the selected template, fall
    /// back to the first supported channel.
    private func reconcileChannel() {
        guard let selectedTemplate else { return }
        if !selectedTemplate.supports(channel) {
            channel = availableChannels.first ?? .call
        }
    }

    /// Templates grouped by category in display order — used by the picker.
    public var templatesByCategory: [(category: TemplateCategory, templates: [TemplateSummary])] {
        Dictionary(grouping: templates, by: \.category)
            .map { ($0.key, $0.value.sorted { $0.displayName < $1.displayName }) }
            .sorted { $0.category.sortOrder < $1.category.sortOrder }
    }

    // MARK: Actions

    public func send() async {
        guard let template = selectedTemplate else { return }
        // Multiple jobs may be queued (up to the backend cap); the backend is the
        // single source of truth and returns active_request_exists only when the
        // cap is actually exceeded. No client-side block here.
        isSubmitting = true
        errorMessage = nil
        defer { isSubmitting = false }
        let draft = RequestDraft(templateID: template.id, channel: channel, timing: timing)
        do {
            let request = try await requestService.create(draft)
            lastCreatedChannel = request.channel
            createdJobCount += 1
            prefs.lastChannel = channel.rawValue
            prefs.lastTimingDelay = timing.delaySeconds
            // Reflect the credit spend and re-derive the "next job" (soonest of
            // possibly several pending) from the backend — not the one just added.
            await refreshProfileQuietly()
            activeRequest = profile?.activeRequest
            // After the send is accepted, optionally suggest saving the sender as
            // a contact. This never blocks scheduling and only appears the first
            // time a binding is seen on this device.
            maybeOfferContactPrompt(for: request)
        } catch {
            // If a parallel request already exists, surface its state.
            if case let .api(code, _, _, _) = asAPIError(error), code == "active_request_exists" {
                await refreshProfileQuietly()
                activeRequest = profile?.activeRequest
            }
            handle(error)
        }
    }

    /// Re-derive the "next job" chip from the backend's soonest live request
    /// (handles a job firing/finishing and surfaces the next pending one).
    public func refreshActiveRequest() async {
        await refreshProfileQuietly()
        activeRequest = profile?.activeRequest
    }

    public func cancelActive() async {
        guard let id = activeRequest?.id else { return }
        errorMessage = nil
        do {
            _ = try await requestService.cancel(id: id)
            // Re-derive the chip from the backend: the next-soonest pending job,
            // or nil if that was the last one.
            await refreshProfileQuietly()
            activeRequest = profile?.activeRequest
        } catch {
            handle(error)
        }
    }

    public func clearActiveRequest() { activeRequest = nil }

    // MARK: Save Contact flow

    /// Decide whether to show the post-success contact prompt. Continuity comes
    /// from the backend binding regardless, so this is purely a convenience.
    func maybeOfferContactPrompt(for request: RequestSummary) {
        guard let sender = request.senderIdentity,
              sender.contactPromptRecommended,
              sender.canSaveContact,
              contactLinks.shouldOfferPrompt(forBinding: sender.bindingID)
        else { return }
        pendingSenderPrompt = sender
    }

    /// User tapped "Save" on the soft prompt: request access in-context if
    /// needed, then either present the contact sheet or explain the denial.
    public func acceptContactPrompt() async {
        guard let sender = pendingSenderPrompt else { return }
        pendingSenderPrompt = nil
        await beginSaveContact(for: sender)
    }

    /// User tapped "Not now" on the soft prompt (or it was auto-dismissed).
    public func skipContactPrompt() {
        guard let sender = pendingSenderPrompt else { return }
        markPromptSkipped(for: sender)
    }

    /// Record a skip for a specific binding. Used by the prompt's "Not now"
    /// button, which passes the captured sender so it can't race the alert's
    /// own dismissal clearing `pendingSenderPrompt`.
    public func markPromptSkipped(for sender: SenderIdentity) {
        pendingSenderPrompt = nil
        recordContactStatus(.notNow, for: sender)
    }

    /// Shared entry point usable from the prompt's "Save" button and re-entry
    /// surfaces (e.g. history detail).
    public func beginSaveContact(for sender: SenderIdentity) async {
        pendingSenderPrompt = nil
        guard sender.canSaveContact else { return }
        var status = contacts.authorizationStatus()
        if status == .notDetermined {
            status = await contacts.requestAccess()
        }
        if status.canPresentContactSheet {
            contactSheetSender = sender
        } else {
            recordContactStatus(.denied, for: sender)
            contactPermissionDeniedSender = sender
        }
    }

    /// Called when the contact sheet finishes. `identifier` is non-nil only when
    /// the user actually saved the contact.
    public func contactSheetFinished(savedIdentifier identifier: String?) {
        guard let sender = contactSheetSender else { return }
        contactSheetSender = nil
        if let identifier {
            recordContactStatus(.created, for: sender, contactIdentifier: identifier)
        } else {
            recordContactStatus(.dismissed, for: sender)
        }
    }

    public func dismissPermissionDeniedNotice() {
        contactPermissionDeniedSender = nil
    }

    private func recordContactStatus(_ status: ContactLinkStatus,
                                     for sender: SenderIdentity,
                                     contactIdentifier: String? = nil) {
        let previous = contactLinks.state(forBinding: sender.bindingID)
        let state = ContactLinkState(
            senderBindingID: sender.bindingID,
            contactStatus: status,
            iosContactIdentifier: contactIdentifier ?? previous?.iosContactIdentifier,
            lastPromptedAt: Date(),
            createdAt: status == .created ? Date() : previous?.createdAt
        )
        contactLinks.save(state)
    }

    // MARK: Helpers

    private func refreshProfileQuietly() async {
        if let updated = try? await profileService.me() {
            profile = updated
        }
    }

    private func handle(_ error: Error) {
        let apiError = asAPIError(error)
        if apiError.requiresReauth {
            onSessionExpired?()
            return
        }
        errorMessage = ErrorCopy.userMessage(for: apiError)
    }
}
