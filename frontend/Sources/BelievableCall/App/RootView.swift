#if canImport(SwiftUI)
import SwiftUI

/// Root surface. Switches between launch, the auth flow, and the main tab bar
/// based on the single top-level `AppModel.Phase`.
public struct RootView: View {
    @State private var app: AppModel

    public init(app: AppModel) {
        _app = State(initialValue: app)
    }

    /// Held true until both the splash minimum has elapsed and session restore
    /// has finished, so the loading screen is always briefly visible.
    @State private var showLaunch = true

    public var body: some View {
        Group {
            if showLaunch {
                LaunchView()
            } else if app.phase == .authenticated {
                MainTabView(app: app)
                    .id(app.session?.token ?? "none")
            } else {
                AuthContainer(app: app)
            }
        }
        .animation(.easeInOut(duration: 0.35), value: showLaunch)
        .task {
            if app.phase == .launching { app.restore() }
            // Minimum on-screen time for the splash even when there's nothing
            // to load.
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            showLaunch = false
        }
    }
}

struct LaunchView: View {
    var body: some View {
        ZStack {
            Theme.backgroundGradient.ignoresSafeArea()
            VStack(spacing: Spacing.l) {
                Image("LaunchLogo", bundle: .module)
                    .resizable()
                    .scaledToFit()
                    .frame(maxWidth: 180, maxHeight: 180)
                    .accessibilityHidden(true)
                ProgressView()
                    .tint(Theme.accent)
            }
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
    enum Tab: Hashable { case home, history, settings }

    @State private var home: HomeViewModel
    @State private var history: HistoryViewModel
    @State private var settings: SettingsViewModel
    @State private var selection: Tab = .home

    init(app: AppModel) {
        _home = State(initialValue: app.makeHomeViewModel())
        _history = State(initialValue: app.makeHistoryViewModel())
        _settings = State(initialValue: app.makeSettingsViewModel())
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            screens
            FloatingTabBar(selection: $selection)
                .padding(.bottom, Spacing.xs)
        }
        .tint(Theme.accent)
        // The screens stay resident, so onAppear only fires once. Refresh the
        // relevant view model each time its tab becomes visible so balances and
        // history reflect actions taken on another tab (e.g. buying credits).
        .onChange(of: selection) { _, newValue in
            switch newValue {
            case .home: Task { await home.refresh() }
            case .history: Task { await history.load() }
            case .settings: break
            }
        }
    }

    // All three screens stay resident so per-tab state and scroll position
    // survive switching; only the selected one is visible and interactive.
    private var screens: some View {
        ZStack {
            HomeView(vm: home, onOpenVerifiedNumber: { selection = .settings })
                .opacity(selection == .home ? 1 : 0)
                .allowsHitTesting(selection == .home)
            HistoryView(vm: history)
                .opacity(selection == .history ? 1 : 0)
                .allowsHitTesting(selection == .history)
            SettingsView(vm: settings)
                .opacity(selection == .settings ? 1 : 0)
                .allowsHitTesting(selection == .settings)
        }
        // Reserve room so scrolling content clears the floating bar.
        .safeAreaInset(edge: .bottom) {
            Color.clear.frame(height: FloatingTabBar.reservedClearance)
        }
    }
}

/// A detached, glassy tab bar that floats above the screen backdrop. Chrome only
/// — it drives the same three destinations. Home is a raised circular button
/// in the middle (showing the app logo); History and Settings flank it.
struct FloatingTabBar: View {
    @Binding var selection: MainTabView.Tab

    /// Vertical space the bar (plus the raised center button + margins) occupies;
    /// screens inset their scroll content by this much so nothing hides behind it.
    static let reservedClearance: CGFloat = 96

    private let centerDiameter: CGFloat = 64
    private let centerLift: CGFloat = 18

    var body: some View {
        ZStack {
            // The pill bar with the two side destinations and a gap for the
            // raised Home button.
            HStack(spacing: 0) {
                sideItem(.history, icon: "clock.fill", label: "History")
                Spacer(minLength: centerDiameter)
                sideItem(.settings, icon: "gearshape.fill", label: "Settings")
            }
            .padding(.horizontal, Spacing.l)
            .padding(.vertical, Spacing.s)
            .background(.ultraThinMaterial, in: Capsule())
            .overlay(Capsule().strokeBorder(Theme.glassBorder, lineWidth: 1))
            .shadow(color: Theme.cardShadow, radius: 18, x: 0, y: 10)

            homeButton
                .offset(y: -centerLift)
        }
        .padding(.horizontal, Spacing.xl)
        .padding(.top, centerLift)
        .animation(.spring(response: 0.35, dampingFraction: 0.8), value: selection)
    }

    private var homeButton: some View {
        let isSelected = selection == .home
        return Button {
            Haptics.play(.impact)
            selection = .home
        } label: {
            Image("AppLogo", bundle: .module)
                .resizable()
                .scaledToFit()
                .padding(centerDiameter * 0.22)
                .frame(width: centerDiameter, height: centerDiameter)
                .background(.regularMaterial, in: Circle())
                .overlay(
                    Circle().strokeBorder(
                        isSelected ? Theme.accent : Theme.glassBorder,
                        lineWidth: isSelected ? 2.5 : 1
                    )
                )
                .shadow(color: Theme.cardShadow, radius: 12, x: 0, y: 6)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Home")
        .accessibilityAddTraits(isSelected ? [.isButton, .isSelected] : .isButton)
    }

    @ViewBuilder
    private func sideItem(_ tab: MainTabView.Tab, icon: String, label: String) -> some View {
        let isSelected = selection == tab
        Button {
            Haptics.play(.impact)
            selection = tab
        } label: {
            VStack(spacing: 2) {
                Image(systemName: icon).font(.body)
                Text(label).font(.caption2.weight(.medium))
            }
            .foregroundStyle(isSelected ? Theme.accent : Color.secondary)
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
        .accessibilityAddTraits(isSelected ? [.isButton, .isSelected] : .isButton)
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
