import SwiftUI
import BelievableCall

/// iOS app entry point. The whole app lives in the `BelievableCall` Swift
/// package; this target is the thin runnable shell that hosts it.
///
/// The backend base URL defaults to the local dev server. For a device build,
/// set `BC_BACKEND_URL` in the scheme's environment, or change the default.
@main
struct BelievableCallApp: App {
    @State private var app: AppModel = {
        let urlString = ProcessInfo.processInfo.environment["BC_BACKEND_URL"]
            ?? "http://127.0.0.1:8000"
        let baseURL = URL(string: urlString) ?? URL(string: "http://127.0.0.1:8000")!
        return AppModel(env: .live(baseURL: baseURL))
    }()

    var body: some Scene {
        WindowGroup {
            RootView(app: app)
        }
    }
}
