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
    enum Tab: Hashable { case history, templates, home, profile, settings }

    @State private var home: HomeViewModel
    @State private var history: HistoryViewModel
    @State private var templates: TemplatesViewModel
    @State private var profile: ProfileViewModel
    @State private var settings: SettingsViewModel
    @State private var selection: Tab = .home
    /// Where Settings should scroll to when Home opens it.
    @State private var settingsFocus: SettingsFocus?
    /// Set when a job is created, to drive the one-shot "fly to History" badge.
    @State private var flyingJob: (id: Int, channel: Channel)?

    init(app: AppModel) {
        _home = State(initialValue: app.makeHomeViewModel())
        _history = State(initialValue: app.makeHistoryViewModel())
        _templates = State(initialValue: app.makeTemplatesViewModel())
        _profile = State(initialValue: app.makeProfileViewModel())
        _settings = State(initialValue: app.makeSettingsViewModel())
    }

    var body: some View {
        // A new user plans their first alibi before seeing the tabs. Home's
        // view model drives both, and only one of them is on screen, so the
        // save-contact sheets have a single owner.
        if home.needsFirstAlibi {
            FirstAlibiView(vm: home) {
                selection = .home
                Task { await home.refresh() }
            }
            .transition(.opacity)
        } else {
            tabs
        }
    }

    private var tabs: some View {
        ZStack(alignment: .bottom) {
            screens
            FloatingTabBar(selection: $selection)
                .padding(.bottom, Spacing.xs)
        }
        // A job, when created on Home, animates a badge flying into the History
        // tab (front-most so it reads over everything; never intercepts taps).
        .overlay {
            if let flyingJob {
                GeometryReader { geo in
                    FlyingJobBadge(
                        systemImage: flyingJob.channel.systemImage,
                        start: CGPoint(x: geo.size.width * 0.5, y: geo.size.height * 0.52),
                        end: CGPoint(x: geo.size.width * 0.18, y: geo.size.height - 54)
                    )
                    .id(flyingJob.id)
                }
                .allowsHitTesting(false)
            }
        }
        .tint(Theme.accent)
        // The screens stay resident, so onAppear only fires once. Refresh the
        // relevant view model each time its tab becomes visible so balances,
        // history, and templates reflect actions taken on another tab.
        .onChange(of: selection) { _, newValue in
            switch newValue {
            case .home: Task { await home.refresh() }
            case .history: Task { await history.load() }
            case .templates: Task { await templates.load() }
            case .profile, .settings: break
            }
        }
        // Launch the fly-to-History animation whenever a job is created.
        .onChange(of: home.createdJobCount) { _, count in
            guard count > 0 else { return }
            flyingJob = (id: count, channel: home.lastCreatedChannel)
            Task {
                try? await Task.sleep(nanoseconds: 800_000_000)
                if flyingJob?.id == count { flyingJob = nil }
            }
        }
    }

    // All screens stay resident so per-tab state and scroll position survive
    // switching; only the selected one is visible and interactive.
    private var screens: some View {
        ZStack {
            HomeView(vm: home,
                     onOpenSettings: { focus in
                         settingsFocus = focus
                         selection = .settings
                     },
                     onOpenHistory: { selection = .history })
                .opacity(selection == .home ? 1 : 0)
                .allowsHitTesting(selection == .home)
            HistoryView(vm: history)
                .opacity(selection == .history ? 1 : 0)
                .allowsHitTesting(selection == .history)
            NavigationStack { TemplatesView(vm: templates) }
                .opacity(selection == .templates ? 1 : 0)
                .allowsHitTesting(selection == .templates)
            ProfileView(vm: profile)
                .opacity(selection == .profile ? 1 : 0)
                .allowsHitTesting(selection == .profile)
            SettingsView(vm: settings, focus: $settingsFocus)
                .opacity(selection == .settings ? 1 : 0)
                .allowsHitTesting(selection == .settings)
        }
        // NOTE: clearance for the floating bar is reserved *inside* each screen
        // via `.bcTabBarClearance()` — a safeAreaInset here wouldn't reach the
        // scroll/list content nested in each screen's own NavigationStack.
    }
}

extension View {
    /// Reserve bottom space so a screen's scroll/list content can clear the
    /// floating tab bar (and not hide its last rows behind it). Apply to the
    /// scrollable container inside each screen's NavigationStack.
    func bcTabBarClearance() -> some View {
        safeAreaInset(edge: .bottom) {
            Color.clear.frame(height: FloatingTabBar.reservedClearance)
        }
    }
}

/// A one-shot badge that flies from the compose area into the History tab when a
/// job is created — quick visual confirmation that it's queued. Purely cosmetic.
struct FlyingJobBadge: View {
    let systemImage: String
    let start: CGPoint
    let end: CGPoint
    @State private var arrived = false

    var body: some View {
        Image(systemName: systemImage)
            .font(.headline)
            .foregroundStyle(.white)
            .padding(12)
            .background(Theme.accentFill, in: Circle())
            .overlay(Circle().strokeBorder(Theme.glassBorder, lineWidth: 1))
            .shadow(color: Theme.cardShadow, radius: 10, x: 0, y: 6)
            .scaleEffect(arrived ? 0.3 : 1)
            .opacity(arrived ? 0 : 1)
            .position(arrived ? end : start)
            .onAppear {
                Haptics.play(.success)
                withAnimation(.easeIn(duration: 0.65)) { arrived = true }
            }
    }
}

/// Grows the whole label a little while pressed, like Liquid Glass does.
struct PressScaleStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 1.12 : 1)
            .animation(.spring(response: 0.3, dampingFraction: 0.6), value: configuration.isPressed)
    }
}

/// A detached, glassy tab bar that floats above the screen backdrop. Chrome only
/// — Home is a raised circular button in the middle (showing the app logo),
/// symmetrically flanked by two destinations on each side.
struct FloatingTabBar: View {
    @Binding var selection: MainTabView.Tab
    @Environment(\.colorScheme) private var colorScheme

    /// Vertical space the bar (plus the raised center button + margins) occupies;
    /// screens inset their scroll content by this much so nothing hides behind it.
    static let reservedClearance: CGFloat = 96

    private let centerDiameter: CGFloat = 64
    private let centerLift: CGFloat = 18

    var body: some View {
        ZStack {
            // Two destinations on each side, with a centered gap for the raised
            // Home button (keeps the bar symmetric).
            HStack(spacing: 0) {
                sideItem(.history, icon: "clock.fill", label: "History")
                sideItem(.templates, icon: "square.stack.3d.up.fill", label: "Alibis")
                Spacer(minLength: centerDiameter)
                sideItem(.profile, icon: "person.crop.circle.fill", label: "Profile")
                sideItem(.settings, icon: "gearshape.fill", label: "Settings")
            }
            .padding(.horizontal, Spacing.m)
            .padding(.vertical, Spacing.s)
            .bcGlassCapsule()
            // Absorb every tap inside the capsule (gaps, padding, center notch)
            // so nothing behind the floating bar receives it.
            .contentShape(Capsule())
            .shadow(color: Theme.cardShadow, radius: 18, x: 0, y: 10)

            homeButton
                .offset(y: -centerLift)
        }
        .padding(.horizontal, Spacing.l)
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
                // The logo's dark "A" disappears on dark glass: in dark mode it
                // sits on a light disc, like an app icon.
                .padding(colorScheme == .dark ? centerDiameter * 0.08 : 0)
                .background(Circle().fill(Color.white.opacity(colorScheme == .dark ? 0.92 : 0)))
                .padding(centerDiameter * (colorScheme == .dark ? 0.14 : 0.22))
                .frame(width: centerDiameter, height: centerDiameter)
                // Not the interactive glass: it grows on press on its own and
                // leaves the selection ring behind. PressScaleStyle scales
                // glass, logo and ring together. Selected, the glass turns
                // light purple like the other tabs' labels.
                .bcGlassCircle(tint: isSelected ? Theme.accent.opacity(0.3) : nil)
                .overlay(
                    Circle().strokeBorder(
                        isSelected ? Theme.accent : Color.clear,
                        lineWidth: isSelected ? 2.5 : 0
                    )
                )
                .shadow(color: Theme.cardShadow, radius: 12, x: 0, y: 6)
                .contentShape(Circle())
        }
        .buttonStyle(PressScaleStyle())
        .accessibilityLabel("Home screen")
        .accessibilityAddTraits(isSelected ? [.isButton, .isSelected] : .isButton)
    }

    @ViewBuilder
    private func sideItem(_ tab: MainTabView.Tab, icon: String, label: LocalizedStringResource) -> some View {
        let isSelected = selection == tab
        Button {
            Haptics.play(.impact)
            selection = tab
        } label: {
            VStack(spacing: 2) {
                Image(systemName: icon).font(.body)
                // One line: "Einstellungen" shrinks a little instead of wrapping.
                Text(label).font(.caption2.weight(.medium))
                    .lineLimit(1)
                    .minimumScaleFactor(0.75)
            }
            // Like the system tab bar: the labels stop growing at large text
            // sizes, and a long press shows them big instead.
            .dynamicTypeSize(...DynamicTypeSize.large)
            .foregroundStyle(isSelected ? Theme.accent : Color.secondary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, Spacing.xs)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityShowsLargeContentViewer {
            Label { Text(label) } icon: { Image(systemName: icon) }
        }
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
