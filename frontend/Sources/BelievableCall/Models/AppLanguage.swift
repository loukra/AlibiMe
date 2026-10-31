import Foundation

/// The language the app is shown in: German when iOS runs the app in German,
/// English otherwise. New accounts start with it as their call language.
public enum AppLanguage {
    public static var current: String {
        Bundle.main.preferredLocalizations.first?.hasPrefix("de") == true ? "de" : "en"
    }

    /// A time zone by its name in the app's language ("Mitteleuropäische
    /// Zeit" for Europe/Berlin), not its ID.
    public static func timeZoneName(_ identifier: String) -> String {
        TimeZone(identifier: identifier)?
            .localizedName(for: .generic, locale: Locale(identifier: current)) ?? identifier
    }
}
