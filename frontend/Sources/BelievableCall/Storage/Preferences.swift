import Foundation

/// Light client preferences for fast restore: last-used channel, last-used
/// timing preset, the selected template, and a stable device id. The backend
/// remains the source of truth for all durable business state.
public protocol PreferencesStoring: AnyObject, Sendable {
    var selectedTemplateID: String? { get set }
    var lastChannel: String? { get set }
    var lastTimingDelay: Int? { get set }
    /// The alibi the Action Button sends; nil until picked in Settings.
    var quickAlibi: QuickAlibi? { get set }
    var deviceID: String { get }
}

public final class UserDefaultsPreferences: PreferencesStoring, @unchecked Sendable {
    private let defaults: UserDefaults
    private enum Key {
        static let template = "bc.selectedTemplateID"
        static let channel = "bc.lastChannel"
        static let timing = "bc.lastTimingDelay"
        static let quickAlibi = "bc.quickAlibi"
        static let device = "bc.deviceID"
    }

    public init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    public var selectedTemplateID: String? {
        get { defaults.string(forKey: Key.template) }
        set { defaults.set(newValue, forKey: Key.template) }
    }

    public var lastChannel: String? {
        get { defaults.string(forKey: Key.channel) }
        set { defaults.set(newValue, forKey: Key.channel) }
    }

    public var lastTimingDelay: Int? {
        get { defaults.object(forKey: Key.timing) as? Int }
        set { defaults.set(newValue, forKey: Key.timing) }
    }

    public var quickAlibi: QuickAlibi? {
        get {
            defaults.data(forKey: Key.quickAlibi)
                .flatMap { try? JSONDecoder().decode(QuickAlibi.self, from: $0) }
        }
        set {
            defaults.set(newValue.flatMap { try? JSONEncoder().encode($0) }, forKey: Key.quickAlibi)
        }
    }

    public var deviceID: String {
        if let existing = defaults.string(forKey: Key.device) {
            return existing
        }
        let new = UUID().uuidString
        defaults.set(new, forKey: Key.device)
        return new
    }
}

/// In-memory preferences for tests and previews.
public final class InMemoryPreferences: PreferencesStoring, @unchecked Sendable {
    public var selectedTemplateID: String?
    public var lastChannel: String?
    public var lastTimingDelay: Int?
    public var quickAlibi: QuickAlibi?
    public let deviceID: String
    public init(deviceID: String = UUID().uuidString) { self.deviceID = deviceID }
}
