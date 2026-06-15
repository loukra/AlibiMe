#if canImport(SwiftUI)
import SwiftUI

/// Action-first home. Lands here after login and can create a request in a few
/// taps without drilling into a separate form.
public struct HomeView: View {
    @Bindable var vm: HomeViewModel
    @State private var showTemplatePicker = false
    @State private var showSchedule = false
    /// Invoked when the user taps the verified-number card; the tab container
    /// routes this to the Settings tab (where the number lives).
    var onOpenVerifiedNumber: (() -> Void)?

    public init(vm: HomeViewModel, onOpenVerifiedNumber: (() -> Void)? = nil) {
        self.vm = vm
        self.onOpenVerifiedNumber = onOpenVerifiedNumber
    }

    public var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Spacing.l) {
                    if let error = vm.errorMessage {
                        ErrorBanner(error)
                    }
                    verifiedNumberCard
                    if vm.hasActiveRequest, let active = vm.activeRequest {
                        ActiveRequestCard(request: active,
                                          onCancel: { Task { await vm.cancelActive() } },
                                          onRefresh: { Task { await vm.refreshActiveRequest() } })
                    } else {
                        requestComposer
                    }
                    creditsSummary
                }
                .padding(Spacing.m)
                .bcPinScrollWidth()
            }
            .bcVerticalScrollOnly()
            .bcScreenBackground()
            .navigationTitle(greeting)
            .refreshable { await vm.refresh() }
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

    private var greeting: String {
        if let name = vm.profile?.displayName, !name.isEmpty { return "Hi, \(name)" }
        return "Alibi"
    }

    private var verifiedNumberCard: some View {
        Button {
            onOpenVerifiedNumber?()
        } label: {
            Card {
                HStack(spacing: Spacing.m) {
                    Image(systemName: "checkmark.shield.fill")
                        .font(.title2)
                        .foregroundStyle(Theme.success)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Your verified number")
                            .font(.subheadline.weight(.medium))
                        Text(vm.maskedNumber ?? "Not verified")
                            .font(.body)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    if onOpenVerifiedNumber != nil {
                        Image(systemName: "chevron.right").foregroundStyle(.secondary)
                    }
                }
                .accessibilityElement(children: .combine)
                .accessibilityHint("Opens your number in Settings")
            }
        }
        .buttonStyle(.plain)
        .disabled(onOpenVerifiedNumber == nil)
    }

    @ViewBuilder private var requestComposer: some View {
        VStack(alignment: .leading, spacing: Spacing.s) {
            SectionHeader("Template")
            Button { showTemplatePicker = true } label: { selectedTemplateCard }
                .buttonStyle(.plain)
        }
        if vm.availableChannels.count > 1 {
            VStack(alignment: .leading, spacing: Spacing.s) {
                SectionHeader("Channel")
                SegmentedSelector(
                    items: vm.availableChannels.map { SegmentItem(id: $0.id, title: $0.title) },
                    selectedID: vm.channel.id
                ) { id in
                    if let channel = Channel(rawValue: id) { vm.selectChannel(channel) }
                }
            }
        }
        VStack(alignment: .leading, spacing: Spacing.s) {
            SectionHeader("When")
            SegmentedSelector(items: timingSegments, selectedID: selectedTimingID) { id in
                if id == scheduleSegmentID {
                    showSchedule = true
                } else if let option = TimingOption.presets.first(where: { $0.id == id }) {
                    vm.selectTiming(option)
                }
            }
        }
        PrimaryButton(vm.primaryCTATitle, systemImage: vm.channel.systemImage, isLoading: vm.isSubmitting) {
            Haptics.play(.impact)
            Task { await vm.send() }
        }
        .disabled(!vm.canSend)
        .opacity(vm.canSend ? 1 : 0.5)
        if !vm.hasCredits {
            Text("You’re out of credits. Add more in Settings to keep sending.")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
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
        Card {
            HStack(spacing: Spacing.m) {
                VStack(alignment: .leading, spacing: Spacing.xs) {
                    if let template = vm.selectedTemplate {
                        Text(template.displayName)
                            .font(.headline)
                            .foregroundStyle(.primary)
                        if let preview = template.preview(for: vm.channel) ?? template.description {
                            Text(preview)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                        }
                    } else {
                        Text("Choose a template")
                            .font(.headline)
                    }
                }
                Spacer()
                Image(systemName: "chevron.right").foregroundStyle(.secondary)
            }
        }
    }

    private var creditsSummary: some View {
        HStack {
            Image(systemName: "creditcard.fill").foregroundStyle(.secondary)
            Text("\(vm.creditsAvailable) credits available")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Spacer()
        }
        .padding(.horizontal, Spacing.xs)
        .accessibilityElement(children: .combine)
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
