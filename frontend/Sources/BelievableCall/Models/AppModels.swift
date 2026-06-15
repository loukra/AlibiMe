import Foundation

// Product-language models. The UI binds to these, never to the raw DTOs. The
// backend's internal request/template naming stays at the network boundary.

public struct UserProfile: Equatable, Identifiable, Sendable {
    public let id: String
    public var locale: String
    public var timezone: String
    public var displayName: String?
    public var phone: VerifiedPhoneSummary
    public var entitlements: EntitlementSummary
    public var activeRequest: RequestSummary?

    public init(id: String,
                locale: String,
                timezone: String,
                displayName: String?,
                phone: VerifiedPhoneSummary,
                entitlements: EntitlementSummary,
                activeRequest: RequestSummary?) {
        self.id = id
        self.locale = locale
        self.timezone = timezone
        self.displayName = displayName
        self.phone = phone
        self.entitlements = entitlements
        self.activeRequest = activeRequest
    }
}

/// A snapshot of the user's own verified number. There is never a destination
/// number entered in the request flow — delivery always goes here.
public struct VerifiedPhoneSummary: Equatable, Sendable {
    public let maskedNumber: String?
    public var isVerified: Bool { maskedNumber?.isEmpty == false }
    public init(maskedNumber: String?) { self.maskedNumber = maskedNumber }
}

public struct EntitlementSummary: Equatable, Sendable {
    public let creditsAvailable: Int
    public let planCodes: [String]
    public init(creditsAvailable: Int, planCodes: [String]) {
        self.creditsAvailable = creditsAvailable
        self.planCodes = planCodes
    }
    public var hasCredits: Bool { creditsAvailable > 0 }
    /// A friendly plan label, e.g. "Free" or "Credits 5".
    public var planLabel: String {
        guard let code = planCodes.first else { return "No plan" }
        return code.replacingOccurrences(of: "_", with: " ").capitalized
    }
}

public enum TemplateCategory: String, CaseIterable, Sendable {
    case work, family, social, logistics, safety

    public var title: String {
        switch self {
        case .work: return "Work"
        case .family: return "Family"
        case .social: return "Social"
        case .logistics: return "Logistics"
        case .safety: return "Safety"
        }
    }

    /// Display order for grouping in the picker.
    public var sortOrder: Int {
        switch self {
        case .work: return 0
        case .family: return 1
        case .social: return 2
        case .logistics: return 3
        case .safety: return 4
        }
    }
}

public struct TemplateSummary: Equatable, Identifiable, Sendable {
    public let id: String
    public let code: String
    public let displayName: String
    public let description: String?
    public let category: TemplateCategory
    public let callerPersona: String
    public let reasonCode: String
    /// Sender identity, keyed by persona so different templates from the same
    /// persona share a sender. `supportsContactSave` gates the save-contact UI.
    public let senderPersonaKey: String
    public let senderDisplayName: String
    public let supportsContactSave: Bool
    public let supportedChannels: Set<Channel>
    public let callMaxDurationSeconds: Int?
    public let previewOpeningLine: String?
    public let previewSMSBody: String?

    public init(id: String,
                code: String,
                displayName: String,
                description: String?,
                category: TemplateCategory,
                callerPersona: String,
                reasonCode: String,
                senderPersonaKey: String = "",
                senderDisplayName: String = "",
                supportsContactSave: Bool = true,
                supportedChannels: Set<Channel>,
                callMaxDurationSeconds: Int?,
                previewOpeningLine: String?,
                previewSMSBody: String?) {
        self.id = id
        self.code = code
        self.displayName = displayName
        self.description = description
        self.category = category
        self.callerPersona = callerPersona
        self.reasonCode = reasonCode
        self.senderPersonaKey = senderPersonaKey
        self.senderDisplayName = senderDisplayName
        self.supportsContactSave = supportsContactSave
        self.supportedChannels = supportedChannels
        self.callMaxDurationSeconds = callMaxDurationSeconds
        self.previewOpeningLine = previewOpeningLine
        self.previewSMSBody = previewSMSBody
    }

    public func supports(_ channel: Channel) -> Bool {
        supportedChannels.contains(channel)
    }

    /// Preview line appropriate for the chosen channel, if any.
    public func preview(for channel: Channel) -> String? {
        switch channel {
        case .call: return previewOpeningLine
        case .text: return previewSMSBody
        }
    }
}

/// User-facing channel. The wire value (`call`/`sms`) lives only in the mapping.
public enum Channel: String, CaseIterable, Identifiable, Sendable {
    case call
    case text

    public var id: String { rawValue }

    /// The value the backend expects in the request body.
    public var wireValue: String {
        switch self {
        case .call: return "call"
        case .text: return "sms"
        }
    }

    public init?(wireValue: String) {
        switch wireValue {
        case "call": self = .call
        case "sms": self = .text
        default: return nil
        }
    }

    public var title: String {
        switch self {
        case .call: return "Call"
        case .text: return "Text"
        }
    }

    public var systemImage: String {
        switch self {
        case .call: return "phone.fill"
        case .text: return "message.fill"
        }
    }
}

/// A timing preset. `now`/`in30`/`in5min` map to `delay_seconds`; `schedule`
/// carries an exact `Date` within the next 24 hours.
public enum TimingOption: Equatable, Identifiable, Sendable {
    case now
    case in30Seconds
    case in5Minutes
    case schedule(Date)

    public var id: String {
        switch self {
        case .now: return "now"
        case .in30Seconds: return "in30"
        case .in5Minutes: return "in5min"
        case .schedule: return "schedule"
        }
    }

    /// The preset cases (excludes the exact-time variant, which needs a date).
    public static var presets: [TimingOption] { [.now, .in30Seconds, .in5Minutes] }

    public var shortTitle: String {
        switch self {
        case .now: return "Now"
        case .in30Seconds: return "30 sec"
        case .in5Minutes: return "5 min"
        case .schedule: return "Schedule"
        }
    }

    /// `delay_seconds` for preset timings; nil for exact-time scheduling.
    public var delaySeconds: Int? {
        switch self {
        case .now: return 0
        case .in30Seconds: return 30
        case .in5Minutes: return 300
        case .schedule: return nil
        }
    }

    public var scheduledAt: Date? {
        if case let .schedule(date) = self { return date }
        return nil
    }
}

/// Normalized request lifecycle. Maps every backend status into a single small
/// set so no screen invents its own interpretation.
public enum RequestStatus: String, Sendable {
    case scheduled
    case dispatching
    case providerAccepted
    case active
    case completed
    case canceled
    case failed
    case expired
    case unknown

    public init(wireValue: String) {
        switch wireValue {
        case "scheduled": self = .scheduled
        case "dispatching": self = .dispatching
        case "provider_accepted": self = .providerAccepted
        case "active": self = .active
        case "completed": self = .completed
        case "canceled": self = .canceled
        case "failed": self = .failed
        case "expired": self = .expired
        default: self = .unknown
        }
    }

    /// True while the request is still pending/live (not in a terminal state).
    public var isLive: Bool {
        switch self {
        case .scheduled, .dispatching, .providerAccepted, .active:
            return true
        case .completed, .canceled, .failed, .expired, .unknown:
            return false
        }
    }

    public var isTerminal: Bool { !isLive }

    /// Calm, neutral status copy for status/history surfaces.
    public func displayText(for channel: Channel) -> String {
        let noun = channel == .call ? "Call" : "Text"
        switch self {
        case .scheduled: return "\(noun) scheduled"
        case .dispatching: return "\(noun) starting"
        case .providerAccepted: return channel == .call ? "Call ringing" : "Text queued"
        case .active: return "Call in progress"
        case .completed: return "Completed"
        case .canceled: return "Canceled"
        case .failed: return "Failed"
        case .expired: return "Expired"
        case .unknown: return "Updating"
        }
    }
}

/// Stable sender identity returned with a created/fetched SMS request. Continuity
/// comes from the backend binding, not from whether the user saves a contact.
public struct SenderIdentity: Equatable, Identifiable, Sendable {
    public let bindingID: String
    public let personaKey: String?
    public let displayName: String?
    public let phoneE164: String?
    public let contactPromptRecommended: Bool

    public var id: String { bindingID }

    public init(bindingID: String,
                personaKey: String?,
                displayName: String?,
                phoneE164: String?,
                contactPromptRecommended: Bool) {
        self.bindingID = bindingID
        self.personaKey = personaKey
        self.displayName = displayName
        self.phoneE164 = phoneE164
        self.contactPromptRecommended = contactPromptRecommended
    }

    /// We can only offer to save a contact when we actually have a number.
    public var canSaveContact: Bool { (phoneE164?.isEmpty == false) }
}

/// Local-device record of whether the user saved the sender as a contact. This
/// is a convenience layer — never the source of truth for sender assignment.
public enum ContactLinkStatus: String, Sendable, Codable {
    case unknown
    case created
    case dismissed
    case denied
    case notNow = "not_now"
}

public struct ContactLinkState: Equatable, Sendable, Codable {
    public let senderBindingID: String
    public var contactStatus: ContactLinkStatus
    public var iosContactIdentifier: String?
    public var lastPromptedAt: Date?
    public var createdAt: Date?

    public init(senderBindingID: String,
                contactStatus: ContactLinkStatus = .unknown,
                iosContactIdentifier: String? = nil,
                lastPromptedAt: Date? = nil,
                createdAt: Date? = nil) {
        self.senderBindingID = senderBindingID
        self.contactStatus = contactStatus
        self.iosContactIdentifier = iosContactIdentifier
        self.lastPromptedAt = lastPromptedAt
        self.createdAt = createdAt
    }

    /// Whether the post-success prompt should still be offered automatically.
    public var shouldOfferPrompt: Bool { contactStatus == .unknown }
}

public struct RequestSummary: Equatable, Identifiable, Sendable {
    public let id: String
    public let channel: Channel
    public let status: RequestStatus
    public let scheduledKind: String?
    public let executeAt: Date
    public let requestedAt: Date?
    public let cancelable: Bool
    public let lastErrorCode: String?
    public let senderIdentity: SenderIdentity?

    public init(id: String,
                channel: Channel,
                status: RequestStatus,
                scheduledKind: String?,
                executeAt: Date,
                requestedAt: Date?,
                cancelable: Bool,
                lastErrorCode: String?,
                senderIdentity: SenderIdentity? = nil) {
        self.id = id
        self.channel = channel
        self.status = status
        self.scheduledKind = scheduledKind
        self.executeAt = executeAt
        self.requestedAt = requestedAt
        self.cancelable = cancelable
        self.lastErrorCode = lastErrorCode
        self.senderIdentity = senderIdentity
    }

    /// Seconds remaining until execution, never negative.
    public func secondsRemaining(now: Date = Date()) -> Int {
        max(0, Int(executeAt.timeIntervalSince(now).rounded()))
    }
}

public struct HistoryEntry: Equatable, Identifiable, Sendable {
    public let id: String
    public let channel: Channel
    public let templateLabel: String
    public let requestedAt: Date
    public let status: RequestStatus
    public let durationSeconds: Int?
    public let preview: String?
    public let senderIdentity: SenderIdentity?

    public init(id: String,
                channel: Channel,
                templateLabel: String,
                requestedAt: Date,
                status: RequestStatus,
                durationSeconds: Int?,
                preview: String?,
                senderIdentity: SenderIdentity? = nil) {
        self.id = id
        self.channel = channel
        self.templateLabel = templateLabel
        self.requestedAt = requestedAt
        self.status = status
        self.durationSeconds = durationSeconds
        self.preview = preview
        self.senderIdentity = senderIdentity
    }
}

/// A purchasable (currently free) credit package, as presented in the Add
/// Credits sheet. The backend is the source of truth; the app never invents
/// amounts or pricing.
public struct CreditPackage: Identifiable, Equatable, Sendable {
    public var id: String { code }
    public let code: String
    public let displayName: String
    public let credits: Int
    public let fulfillmentMode: String
    public let priceLabel: String
    public let badgeText: String?
    public let sortOrder: Int

    public init(code: String,
                displayName: String,
                credits: Int,
                fulfillmentMode: String,
                priceLabel: String,
                badgeText: String?,
                sortOrder: Int) {
        self.code = code
        self.displayName = displayName
        self.credits = credits
        self.fulfillmentMode = fulfillmentMode
        self.priceLabel = priceLabel
        self.badgeText = badgeText
        self.sortOrder = sortOrder
    }
}

/// Result of acquiring a credit package — the authoritative post-grant balance.
public struct CreditAcquisition: Equatable, Sendable {
    public let claimID: String
    public let status: String
    public let grantedCredits: Int
    public let creditsAvailable: Int
    public let planCode: String

    public init(claimID: String, status: String, grantedCredits: Int, creditsAvailable: Int, planCode: String) {
        self.claimID = claimID
        self.status = status
        self.grantedCredits = grantedCredits
        self.creditsAvailable = creditsAvailable
        self.planCode = planCode
    }
}

/// Authenticated session as the app holds it locally.
public struct Session: Equatable, Sendable {
    public let token: String
    public let userID: String
    public let maskedNumber: String?
    public init(token: String, userID: String, maskedNumber: String?) {
        self.token = token
        self.userID = userID
        self.maskedNumber = maskedNumber
    }
}
