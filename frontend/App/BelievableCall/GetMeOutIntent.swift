import AppIntents
import BelievableCall

/// "Get Me Out": sends the quick alibi picked in Settings without opening the
/// app. Shows up for the Action Button, Siri and the Shortcuts app.
struct GetMeOutIntent: AppIntent {
    static let title: LocalizedStringResource = "Get Me Out"
    static let description = IntentDescription("Sends your quick alibi: a call or text from the contact you picked.")
    static let openAppWhenRun = false

    @Parameter(title: "When", description: "Overrides the timing from Settings.")
    var timing: AlibiTiming?

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let runner = QuickAlibiRunner(env: .live(baseURL: Backend.url, storeKit: false))
        do {
            let message = try await runner.run(delaySeconds: timing?.delaySeconds)
            return .result(dialog: IntentDialog(stringLiteral: message))
        } catch let error as QuickAlibiError {
            throw GetMeOutError(message: error.message)
        }
    }
}

enum AlibiTiming: String, AppEnum {
    case now, in30Seconds, in5Minutes

    static let typeDisplayRepresentation: TypeDisplayRepresentation = "Timing"
    static let caseDisplayRepresentations: [AlibiTiming: DisplayRepresentation] = [
        .now: "Now",
        .in30Seconds: "In 30 seconds",
        .in5Minutes: "In 5 minutes",
    ]

    var delaySeconds: Int {
        switch self {
        case .now: return 0
        case .in30Seconds: return 30
        case .in5Minutes: return 300
        }
    }
}

struct GetMeOutError: Error, CustomLocalizedStringResourceConvertible {
    let message: String
    var localizedStringResource: LocalizedStringResource { "\(message)" }
}

struct AlibiShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: GetMeOutIntent(),
            phrases: [
                "Get me out with \(.applicationName)",
                "\(.applicationName), call me",
                "Start \(.applicationName)",
            ],
            shortTitle: "Get Me Out",
            systemImageName: "phone.arrow.down.left"
        )
    }
}
