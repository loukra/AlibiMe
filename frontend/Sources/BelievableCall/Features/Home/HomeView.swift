#if canImport(SwiftUI)
import SwiftUI

/// Action-first home. Lands here after login and can create a request in a few
/// taps without drilling into a separate form.
public struct HomeView: View {
    @Bindable var vm: HomeViewModel
    @State private var showTemplatePicker = false
    @State private var showSchedule = false
    /// The taller of the two cards (next job, template); both take it, so
    /// the screen keeps its shape whatever they show.
    @State private var cardHeight: CGFloat = 0
    /// Invoked from the number and credits pills; the tab container opens the
    /// Settings tab at the part that was tapped.
    var onOpenSettings: ((SettingsFocus) -> Void)?
    /// Invoked when the user taps the "next job" chip body — opens History.
    var onOpenHistory: (() -> Void)?

    public init(vm: HomeViewModel,
                onOpenSettings: ((SettingsFocus) -> Void)? = nil,
                onOpenHistory: (() -> Void)? = nil) {
        self.vm = vm
        self.onOpenSettings = onOpenSettings
        self.onOpenHistory = onOpenHistory
    }

    public var body: some View {
        NavigationStack {
            // One screen, no scrolling: a compact header instead of a large
            // title, the button pinned above the tab bar. Only a screen too short
            // for it (iPhone SE, large text) falls back to scrolling.
            ViewThatFits(in: .vertical) {
                composer(pinned: true)
                ScrollView {
                    composer(pinned: false)
                        .bcPinScrollWidth()
                }
                .bcVerticalScrollOnly()
                .refreshable { await vm.refresh() }
            }
            .bcTabBarClearance()
            .bcScreenBackground()
            .bcHiddenNavigationBar()
            .task { if vm.templates.isEmpty { await vm.load() } }
            .sheet(isPresented: $showTemplatePicker) {
                TemplatePickerView(vm: vm) { showTemplatePicker = false }
            }
            .sheet(isPresented: $showSchedule) {
                ScheduleSheet(timezone: vm.profile?.timezone ?? "UTC") { date in
                    showSchedule = false
                    vm.selectTiming(.schedule(date))
                    Haptics.play(.impact)
                    Task { await vm.send() }
                } onCancel: {
                    showSchedule = false
                }
            }
            .saveContactFlow(vm: vm)
        }
    }

    /// `pinned` pushes the send button to the bottom of the screen.
    private func composer(pinned: Bool) -> some View {
        VStack(alignment: .leading, spacing: Spacing.m) {
            header
            if let error = vm.errorMessage {
                ErrorBanner(error)
            }
            // Only while something is scheduled; an empty "nothing
            // scheduled" card would push the actual choice down.
            if vm.hasActiveRequest, let request = vm.activeRequest {
                NextJobChip(request: request,
                            minHeight: cardHeight,
                            onCancel: { Haptics.play(.warning); Task { await vm.cancelActive() } },
                            onOpen: { onOpenHistory?() })
            }
            requestComposer
            if pinned { Spacer(minLength: Spacing.s) }
            sendButton
        }
        .padding(.horizontal, Spacing.m)
        .padding(.top, Spacing.s)
        .padding(.bottom, Spacing.m)
        .onPreferenceChange(CardHeightKey.self) { cardHeight = $0 }
    }

    /// The verified number and the credits, as two small pills. Each opens
    /// Settings at its own section.
    private var header: some View {
        HStack(spacing: Spacing.s) {
            pill(systemImage: "checkmark.shield.fill", tint: Theme.success,
                 text: vm.maskedNumber ?? "Not verified", opens: .number)
                .accessibilityLabel("Your verified number, \(vm.maskedNumber ?? "not verified")")
            Spacer(minLength: 0)
            pill(systemImage: "creditcard.fill",
                 tint: vm.hasCredits ? Color.secondary : Theme.destructive,
                 text: vm.creditsAvailable == 1 ? "1 credit" : "\(vm.creditsAvailable) credits",
                 opens: .credits)
                .accessibilityLabel("\(vm.creditsAvailable) credits available")
        }
    }

    private func pill(systemImage: String, tint: Color, text: String,
                      opens focus: SettingsFocus) -> some View {
        Button { onOpenSettings?(focus) } label: {
            HStack(spacing: Spacing.xs + 2) {
                Image(systemName: systemImage).foregroundStyle(tint)
                Text(text).foregroundStyle(.primary)
            }
            .font(.subheadline.weight(.medium))
            .padding(.horizontal, Spacing.m)
            .padding(.vertical, Spacing.s)
            .bcGlassCapsule()
            .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .disabled(onOpenSettings == nil)
        .accessibilityHint("Opens Settings")
    }

    @ViewBuilder private var requestComposer: some View {
        VStack(alignment: .leading, spacing: Spacing.s) {
            SectionHeader("Which alibi?")
            Button { showTemplatePicker = true } label: { selectedTemplateCard }
                .buttonStyle(.plain)
        }
        if vm.availableChannels.count > 1 {
            VStack(alignment: .leading, spacing: Spacing.s) {
                SectionHeader("Call or text?")
                SegmentedSelector(
                    items: vm.availableChannels.map { SegmentItem(id: $0.id, title: $0.title) },
                    selectedID: vm.channel.id
                ) { id in
                    if let channel = Channel(rawValue: id) { vm.selectChannel(channel) }
                }
            }
        }
        VStack(alignment: .leading, spacing: Spacing.s) {
            SectionHeader("When?")
            SegmentedSelector(items: timingSegments, selectedID: selectedTimingID) { id in
                if id == scheduleSegmentID {
                    showSchedule = true
                } else if let option = TimingOption.presets.first(where: { $0.id == id }) {
                    vm.selectTiming(option)
                }
            }
        }
    }

    @ViewBuilder private var sendButton: some View {
        if !vm.hasCredits {
            Button { onOpenSettings?(.addCredits) } label: {
                Text("You’re out of credits. Tap to add more.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.plain)
        }
        PrimaryButton(vm.primaryCTATitle, systemImage: vm.channel.systemImage, isLoading: vm.isSubmitting) {
            Haptics.play(.impact)
            Task { await vm.send() }
        }
        .disabled(!vm.canSend)
        .opacity(vm.canSend ? 1 : 0.5)
    }

    private var isScheduling: Bool {
        if case .schedule = vm.timing { return true }
        return false
    }

    private let scheduleSegmentID = "schedule"

    /// The "When" options as segments: the presets plus a Schedule entry.
    private var timingSegments: [SegmentItem] {
        TimingOption.presets.map { SegmentItem(id: $0.id, title: $0.shortTitle) }
            + [SegmentItem(id: scheduleSegmentID, title: "Schedule")]
    }

    private var selectedTimingID: String {
        isScheduling ? scheduleSegmentID : vm.timing.id
    }

    @ViewBuilder private var selectedTemplateCard: some View {
        Card(minHeight: cardHeight) {
            HStack(spacing: Spacing.m) {
                IconBadge(vm.selectedTemplate?.category.systemImage ?? "square.stack.3d.up")
                VStack(alignment: .leading, spacing: Spacing.xs) {
                    if let template = vm.selectedTemplate {
                        Text(template.displayName)
                            .font(.headline)
                            .foregroundStyle(.primary)
                            .lineLimit(2)
                        // Always two lines tall, so switching between Call and
                        // Text (whose previews differ in length) doesn't move
                        // the controls below.
                        Text(template.preview(for: vm.channel) ?? template.description ?? "")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .lineLimit(2, reservesSpace: true)
                    } else {
                        Text("Choose an alibi")
                            .font(.headline)
                    }
                }
                Spacer()
                Image(systemName: "chevron.right").foregroundStyle(.secondary)
            }
        }
    }
}

struct HomeView_Previews: PreviewProvider {
    static var previews: some View {
        HomeView(vm: HomeViewModel(templateService: MockTemplateService(),
                                   requestService: MockRequestService(),
                                   profileService: MockProfileService(),
                                   prefs: InMemoryPreferences(),
                                   contacts: MockContactsService(),
                                   contactLinks: InMemoryContactLinkStore()))
    }
}
#endif
