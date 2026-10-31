import Foundation

/// The language the app is shown in: German when iOS runs the app in German,
/// English otherwise. New accounts start with it as their call language.
public enum AppLanguage {
    public static var current: String {
        Bundle.main.preferredLocalizations.first?.hasPrefix("de") == true ? "de" : "en"
    }
}
