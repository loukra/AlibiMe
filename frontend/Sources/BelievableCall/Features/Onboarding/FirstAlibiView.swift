#if canImport(SwiftUI)
import SwiftUI

/// The walkthrough a new user sees before anything else: they plan their first
/// alibi for a real moment coming up, as a text, and save its sender as a
/// contact right away, so the text already shows up under that name when it
/// arrives. A tutorial that is also the first real use, not a throwaway test.
struct FirstAlibiView: View {
    @Bindable var vm: HomeViewModel
    let onFinish: () -> Void

    enum Step: Equatable {
        case intro, alibi, when
        case contact(RequestSummary, SenderIdentity)
        case done(RequestSummary)
    }

    @State private var step: Step = .intro
    @State private var template: TemplateSummary?
    @State private var timing: TimingOption = .in5Minutes
    @State private var showSchedule = false
    /// Waiting for the contact sheet (or the permission notice) to close.
    @State private var savingContact = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Spacing.l) {
                    content
                }
                .padding(Spacing.l)
                .bcPinScrollWidth()
            }
            .bcVerticalScrollOnly()
            .safeAreaInset(edge: .bottom) {
                actions
                    .padding(.horizontal, Spacing.l)
                    .padding(.bottom, Spacing.s)
            }
            .bcScreenBackground()
            .toolbar { toolbar }
            .animation(.easeInOut(duration: 0.25), value: step)
            .sheet(isPresented: $showSchedule) {
                ScheduleSheet(timezone: vm.profile?.timezone ?? "UTC") { date in
                    showSchedule = false
                    timing = .schedule(date)
                } onCancel: {
                    showSchedule = false
                }
            }
            .saveContactFlow(vm: vm)
            .onChange(of: vm.contactSheetSender == nil && vm.contactPermissionDeniedSender == nil) { _, closed in
                guard closed, savingContact, case let .contact(request, _) = step else { return }
                savingContact = false
                step = .done(request)
            }
        }
    }

    // MARK: Steps

    @ViewBuilder
    private var content: some View {
        switch step {
        case .intro:
            heading(String(localized: "Your first alibi"),
                    String(localized: "Plan it for a real moment coming up, like tonight's date or tomorrow's meeting. It comes as a text, so you see how it works, and it uses one of your credits."))
        case .alibi:
            heading(String(localized: "Who gets you out?"), String(localized: "Pick the alibi that fits. You can write your own later."))
            ForEach(vm.firstAlibiChoices) { choice in
                TemplateCard(template: choice, isSelected: choice.id == template?.id) {
                    template = choice
                    Haptics.play(.impact)
                    step = .when
                }
            }
        case .when:
            heading(String(localized: "When do you need it?"), String(localized: "The text arrives then. Until it goes out, you can cancel it in History."))
            timingChoices
            if let preview = template?.previewSMSBody, let template {
                VStack(alignment: .leading, spacing: Spacing.s) {
                    SectionHeader("What \(template.senderDisplayName) writes")
                    Card {
                        Text(preview)
                            .font(.body)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
            if let error = vm.errorMessage {
                ErrorBanner(error)
            }
        case let .contact(_, sender):
            let name = sender.displayName ?? String(localized: "Contact")
            heading(String(localized: "One more thing"),
                    String(localized: "\(name) always texts and calls you from the same number. Save it as a contact now, and when the text comes, your phone shows \(name) like any other message."))
        case let .done(request):
            let name = request.senderIdentity?.displayName ?? template?.senderDisplayName ?? String(localized: "Contact")
            heading(String(localized: "You're set"),
                    String(localized: "\(name) texts you \(ScheduleSheet.describe(request.executeAt))."))
            VStack(alignment: .leading, spacing: Spacing.s) {
                tip("xmark.circle", "Changed your mind? Cancel it in History before it goes out.")
                // The text holds its credit only when it goes out, so count it here already.
                let left = vm.creditsAvailable - vm.textCost
                if let costs = vm.profile?.creditCosts, left >= costs.call {
                    tip("phone", "You still have \(left) credits, enough for a call next time.")
                }
            }
        }
    }

    private var timingChoices: some View {
        VStack(spacing: Spacing.s) {
            timingRow(String(localized: "In 5 minutes"), selected: timing == .in5Minutes) {
                timing = .in5Minutes
            }
            timingRow(scheduledTitle, selected: timing.scheduledAt != nil) {
                showSchedule = true
            }
        }
    }

    private var scheduledTitle: String {
        if let date = timing.scheduledAt {
            return String(localized: "At \(ScheduleSheet.clockTime(date))")
        }
        return String(localized: "At a time…")
    }

    // MARK: Buttons

    @ViewBuilder
    private var actions: some View {
        switch step {
        case .intro:
            VStack(spacing: Spacing.s) {
                PrimaryButton(String(localized: "Plan my first alibi")) { step = .alibi }
                Button("Later", action: finish)
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(Theme.accent)
            }
        case .alibi:
            EmptyView()
        case .when:
            PrimaryButton(sendTitle, systemImage: "message.fill", isLoading: vm.isSubmitting) {
                Task { await send() }
            }
            .disabled(template == nil)
        case let .contact(request, sender):
            VStack(spacing: Spacing.s) {
                PrimaryButton(String(localized: "Save as \(sender.displayName ?? String(localized: "Contact"))"),
                              systemImage: "person.crop.circle.badge.plus") {
                    savingContact = true
                    Task { await vm.beginSaveContact(for: sender) }
                }
                Button("Skip") {
                    vm.markPromptSkipped(for: sender)
                    step = .done(request)
                }
                .font(.subheadline.weight(.medium))
                .foregroundStyle(Theme.accent)
            }
        case .done:
            PrimaryButton("Done", action: finish)
        }
    }

    private var sendTitle: String {
        vm.textCost == 1 ? String(localized: "Plan this text · 1 credit")
            : String(localized: "Plan this text · \(vm.textCost) credits")
    }

    @ToolbarContentBuilder
    private var toolbar: some ToolbarContent {
        if step == .alibi || step == .when {
            ToolbarItem(placement: .cancellationAction) {
                Button {
                    step = step == .when ? .alibi : .intro
                } label: {
                    Image(systemName: "chevron.left")
                }
                .accessibilityLabel("Back")
            }
            ToolbarItem(placement: .confirmationAction) {
                Button("Later", action: finish)
            }
        }
    }

    // MARK: Actions

    private func send() async {
        guard let template else { return }
        Haptics.play(.impact)
        guard let request = await vm.sendFirstAlibi(template, timing: timing) else { return }
        Haptics.play(.success)
        if let sender = request.senderIdentity, vm.shouldOfferContactSave(for: sender) {
            step = .contact(request, sender)
        } else {
            step = .done(request)
        }
    }

    private func finish() {
        vm.finishFirstAlibi()
        onFinish()
    }

    // MARK: Pieces

    private func heading(_ title: String, _ text: String) -> some View {
        VStack(alignment: .leading, spacing: Spacing.s) {
            Text(title)
                .font(.largeTitle.bold())
                .fixedSize(horizontal: false, vertical: true)
            Text(text)
                .font(.body)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.top, Spacing.m)
    }

    private func tip(_ icon: String, _ text: LocalizedStringResource) -> some View {
        Label {
            Text(text).fixedSize(horizontal: false, vertical: true)
        } icon: {
            Image(systemName: icon).foregroundStyle(Theme.accent)
        }
        .font(.subheadline)
    }

    private func timingRow(_ title: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Card {
                HStack {
                    Text(title).font(.body.weight(.semibold))
                    Spacer()
                    Image(systemName: selected ? "checkmark.circle.fill" : "circle")
                        .foregroundStyle(selected ? Theme.accent : .secondary)
                }
            }
            .overlay(
                RoundedRectangle(cornerRadius: Radius.card, style: .continuous)
                    .strokeBorder(selected ? Theme.accent : Color.clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? [.isButton, .isSelected] : .isButton)
    }
}
#endif
