#if canImport(SwiftUI)
import SwiftUI

/// Root surface. Switches between launch, the auth flow, and the main tab bar
/// based on the single top-level `AppModel.Phase`.
public struct RootView: View {
    @State private var app: AppModel

    public init(app: AppModel) {
        _app = State(initialValue: app)
    }

    public var body: some View {
        Group {
            switch app.phase {
            case .launching:
                LaunchView()
            case .unauthenticated:
                AuthContainer(app: app)
            case .authenticated:
                MainTabView(app: app)
                    .id(app.session?.token ?? "none")
            }
        }
        .onAppear { if app.phase == .launching { app.restore() } }
    }
}

struct LaunchView: View {
    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            ProgressView()
        }
    }
}

/// Owns a fresh `AuthViewModel`, resetting to the start if it reappears after a
/// previous sign-in.
struct AuthContainer: View {
    let app: AppModel
    @State private var vm: AuthViewModel

    init(app: AppModel) {
        self.app = app
        _vm = State(initialValue: app.makeAuthViewModel())
    }

    var body: some View {
        AuthFlowView(vm: vm, sessionExpiredNotice: app.sessionExpiredNotice)
            .onAppear { if vm.step == .done { vm.reset() } }
    }
}

struct MainTabView: View {
    @State private var home: HomeViewModel
    @State private var history: HistoryViewModel
    @State private var settings: SettingsViewModel

    init(app: AppModel) {
        _home = State(initialValue: app.makeHomeViewModel())
        _history = State(initialValue: app.makeHistoryViewModel())
        _settings = State(initialValue: app.makeSettingsViewModel())
    }

    var body: some View {
        TabView {
            HomeView(vm: home)
                .tabItem { Label("Home", systemImage: "house.fill") }
            HistoryView(vm: history)
                .tabItem { Label("History", systemImage: "clock.fill") }
            SettingsView(vm: settings)
                .tabItem { Label("Settings", systemImage: "gearshape.fill") }
        }
        .tint(Theme.accent)
    }
}

struct RootView_Previews: PreviewProvider {
    static var previews: some View {
        let env = AppEnvironment(baseURL: URL(string: "http://127.0.0.1:8000")!,
                                 sessionStore: InMemorySessionStore(session: Session(token: "t", userID: "u", maskedNumber: "+14******123")),
                                 prefs: InMemoryPreferences())
        let app = AppModel(env: env)
        app.restore()
        return RootView(app: app)
    }
}
#endif
