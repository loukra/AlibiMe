import Foundation

/// The alibi the Action Button (or Siri, or a Shortcut) sends without opening
/// the app. Picked once in Settings; stored on the device.
public struct QuickAlibi: Codable, Equatable, Sendable {
    public var templateID: String
    public var templateName: String
    public var channel: Channel
    /// 0, 30 or 300, matching the app's timing presets.
    public var delaySeconds: Int

    public init(templateID: String, templateName: String, channel: Channel, delaySeconds: Int) {
        self.templateID = templateID
        self.templateName = templateName
        self.channel = channel
        self.delaySeconds = delaySeconds
    }

    public var timing: TimingOption {
        switch delaySeconds {
        case 300...: return .in5Minutes
        case 30...: return .in30Seconds
        default: return .now
        }
    }
}

extension Channel: Codable {}

public enum QuickAlibiError: Error, Equatable {
    case signedOut
    case notSetUp
    case failed(String)

    public var message: String {
        switch self {
        case .signedOut: return String(localized: "Open AlibiMe and sign in first.")
        case .notSetUp: return String(localized: "Pick your quick alibi in AlibiMe's settings first.")
        case let .failed(message): return message
        }
    }
}

/// Sends the quick alibi. Used by the App Intent, so it only needs storage and
/// the request service, no UI.
public struct QuickAlibiRunner: Sendable {
    let sessionStore: SessionStoring
    let tokenHolder: TokenHolder
    let prefs: PreferencesStoring
    let requests: RequestServicing

    public init(sessionStore: SessionStoring, tokenHolder: TokenHolder,
                prefs: PreferencesStoring, requests: RequestServicing) {
        self.sessionStore = sessionStore
        self.tokenHolder = tokenHolder
        self.prefs = prefs
        self.requests = requests
    }

    public init(env: AppEnvironment) {
        self.init(sessionStore: env.sessionStore, tokenHolder: env.tokenHolder,
                  prefs: env.prefs, requests: env.requests)
    }

    /// The saved quick alibi, or else whatever was sent last from Home.
    public func resolve() -> QuickAlibi? {
        if let saved = prefs.quickAlibi { return saved }
        guard let templateID = prefs.selectedTemplateID else { return nil }
        let channel = prefs.lastChannel.flatMap(Channel.init(rawValue:)) ?? .call
        return QuickAlibi(templateID: templateID, templateName: "", channel: channel,
                          delaySeconds: prefs.lastTimingDelay ?? 0)
    }

    /// Sends it and returns a short confirmation for Siri / the Action Button
    /// banner. `delaySeconds` overrides the saved timing.
    public func run(delaySeconds: Int? = nil) async throws -> String {
        guard let session = sessionStore.load() else { throw QuickAlibiError.signedOut }
        guard var alibi = resolve() else { throw QuickAlibiError.notSetUp }
        if let delaySeconds { alibi.delaySeconds = delaySeconds }
        tokenHolder.update(session.token)
        do {
            _ = try await requests.create(
                RequestDraft(templateID: alibi.templateID, channel: alibi.channel, timing: alibi.timing)
            )
        } catch {
            let apiError = asAPIError(error)
            if apiError.requiresReauth { throw QuickAlibiError.signedOut }
            throw QuickAlibiError.failed(ErrorCopy.userMessage(for: apiError))
        }
        return Self.confirmation(for: alibi)
    }

    static func confirmation(for alibi: QuickAlibi) -> String {
        switch (alibi.channel, alibi.timing) {
        case (.call, .in30Seconds): return String(localized: "Your call comes in 30 seconds.")
        case (.call, .in5Minutes): return String(localized: "Your call comes in 5 minutes.")
        case (.text, .in30Seconds): return String(localized: "Your text comes in 30 seconds.")
        case (.text, .in5Minutes): return String(localized: "Your text comes in 5 minutes.")
        case (.call, _): return String(localized: "Calling you now.")
        case (.text, _): return String(localized: "Texting you now.")
        }
    }
}
