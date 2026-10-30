import SwiftUI
import BelievableCall

/// iOS app entry point. The whole app lives in the `BelievableCall` Swift
/// package; this target is the thin runnable shell that hosts it.
///
/// The backend base URL comes from the `BC_BACKEND_URL` build setting (see
/// Signing.xcconfig): the local dev server for Debug, the API domain for Release.
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
    /// The build setting baked into Info.plist. Debug builds can override it
    /// with `BC_BACKEND_URL` in the scheme's environment or the app's defaults
    /// (`xcrun simctl spawn booted defaults write com.believablecall.app
    /// BC_BACKEND_URL <url>`); Release builds always use the build setting.
    static var url: URL {
        #if DEBUG
        let override = ProcessInfo.processInfo.environment["BC_BACKEND_URL"]
            ?? UserDefaults.standard.string(forKey: "BC_BACKEND_URL")
        #else
        let override: String? = nil
        #endif
        let configured = Bundle.main.object(forInfoDictionaryKey: "BCBackendURL") as? String
        let urlString = override ?? configured ?? "http://127.0.0.1:8000"
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
