import XCTest

/// The German translation must never fall behind: every text in the app's
/// string catalogs needs a German value with the same placeholders. New texts
/// get into the catalogs with `scripts/strings.sh`; `--check` also catches a
/// text in the code that the catalogs miss.
final class LocalizationTests: XCTestCase {
    private static let catalogDir = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()      // BelievableCallTests
        .deletingLastPathComponent()      // Tests
        .deletingLastPathComponent()      // frontend
        .appendingPathComponent("App/BelievableCall")

    private func strings(_ name: String) throws -> [String: [String: Any]] {
        let data = try Data(contentsOf: Self.catalogDir.appendingPathComponent("\(name).xcstrings"))
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        return json?["strings"] as? [String: [String: Any]] ?? [:]
    }

    /// Like the app name, which stays "AlibiMe" in every language.
    private static func untranslatable(_ entry: [String: Any]) -> Bool {
        entry["shouldTranslate"] as? Bool == false
    }

    private func placeholders(_ text: String) -> [String] {
        let regex = try! NSRegularExpression(pattern: "%(?:\\d+\\$)?(?:lld|ld|d|@|lf|f)")
        return regex.matches(in: text, range: NSRange(text.startIndex..., in: text))
            .map { (text as NSString).substring(with: $0.range).replacingOccurrences(
                of: "\\d+\\$", with: "", options: .regularExpression) }
            .sorted()
    }

    func testEveryTextHasAGermanTranslation() throws {
        var problems: [String] = []
        for (key, entry) in try strings("Localizable") where !Self.untranslatable(entry) {
            if entry["extractionState"] as? String == "stale" {
                problems.append("no longer used, delete it: \(key)")
                continue
            }
            let localizations = entry["localizations"] as? [String: Any]
            let unit = (localizations?["de"] as? [String: Any])?["stringUnit"] as? [String: Any]
            guard unit?["state"] as? String == "translated", let german = unit?["value"] as? String else {
                problems.append("no German: \(key)")
                continue
            }
            if placeholders(german) != placeholders(key) {
                problems.append("placeholders differ: \(key) -> \(german)")
            }
        }
        XCTAssertEqual(problems.sorted(), [], "Run scripts/strings.sh and translate the new texts")
    }

    func testSiriPhrasesAndPermissionTextsHaveGerman() throws {
        for name in ["AppShortcuts", "InfoPlist"] {
            for (key, entry) in try strings(name) where !Self.untranslatable(entry) {
                let german = (entry["localizations"] as? [String: Any])?["de"]
                XCTAssertNotNil(german, "\(name): no German for \(key)")
            }
        }
    }
}
