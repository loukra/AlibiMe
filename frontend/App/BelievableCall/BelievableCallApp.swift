import SwiftUI
import BelievableCall

/// iOS app entry point. The whole app lives in the `BelievableCall` Swift
/// package; this target is the thin runnable shell that hosts it.
///
/// The backend base URL defaults to the local dev server. For a device build,
/// set `BC_BACKEND_URL` in the scheme's environment, or change the default.
/// Debug builds use mock purchases unless `BC_PURCHASES=storekit` (e.g. with
/// the AlibiMe.storekit configuration selected in the scheme).
@main
struct BelievableCallApp: App {
    @State private var app = AppModel(env: .live(baseURL: Backend.url, storeKit: Backend.storeKit))

    var body: some Scene {
        WindowGroup {
            RootView(app: app)
        }
    }
}

enum Backend {
    static var url: URL {
        let urlString = ProcessInfo.processInfo.environment["BC_BACKEND_URL"]
            ?? "http://127.0.0.1:8000"
        return URL(string: urlString) ?? URL(string: "http://127.0.0.1:8000")!
    }

    static var storeKit: Bool {
        #if DEBUG
        return ProcessInfo.processInfo.environment["BC_PURCHASES"] == "storekit"
        #else
        return true
        #endif
    }
}
