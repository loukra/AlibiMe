#if os(iOS)
import SwiftUI

/// iOS app entry point. Builds the live environment (Keychain session storage,
/// real APIClient against the backend) and hands the root model to `RootView`.
///
/// The backend base URL defaults to the local dev server. For a device build,
/// set `BC_BACKEND_URL` in the scheme's environment, or change the default here.
@main
struct BelievableCallApp: App {
    @State private var app: AppModel = {
        let urlString = ProcessInfo.processInfo.environment["BC_BACKEND_URL"]
            ?? "http://127.0.0.1:8000"
        let baseURL = URL(string: urlString) ?? URL(string: "http://127.0.0.1:8000")!
        return AppModel(env: .live(baseURL: baseURL))
    }()

    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView(app: app)
        }
    }
}
#endif
