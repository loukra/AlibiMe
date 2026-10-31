#if canImport(SwiftUI)
import SwiftUI

/// The Profile tab: optional, reusable life-context the composer can use to make
/// custom templates more believable. It lists only what the user has answered;
/// "Add something about you" offers the open questions, one at a time. Every
/// answer is saved as soon as it is picked.
public struct ProfileView: View {
    @Bindable var vm: ProfileViewModel
    /// The open questions when the add sheet was opened. Fixed for the sheet's
    /// lifetime, so a question doesn't vanish while its answers are on screen.
    @State private var adding: AddableQuestions?
    @State private var confirmClear = false

    public init(vm: ProfileViewModel) { self.vm = vm }

    private var questions: [ProfileQuestion] { ProfileQuestion.all(vm.options) }
    private var answered: [ProfileQuestion] { questions.filter { $0.isAnswered(in: vm.profile) } }

    public var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("When you write your own call, the caller can mention your job, your home or your family, so the reason sounds like it's really about you. Add only what you like.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }

                ForEach(ProfileTopic.allCases) { topic in
                    let rows = answered.filter { $0.topic == topic }
                    if !rows.isEmpty {
                        Section {
                            ForEach(rows) { answeredRow($0) }
                        } header: {
                            SectionHeader(topic.title)
                        }
                    }
                }

                Section {
                    Button {
                        adding = AddableQuestions(ids: questions.filter { !$0.isAnswered(in: vm.profile) }.map(\.id))
                    } label: {
                        Label("Add something about you", systemImage: "plus.circle.fill")
                            .font(.body.weight(.semibold))
                            .foregroundStyle(Theme.accent)
                    }
                    .disabled(answered.count == questions.count || vm.phase == .loading)
                }

                if let error = vm.errorMessage {
                    Section { ErrorBanner(error) }
                }

                if !answered.isEmpty {
                    Section {
                        Button(role: .destructive) {
                            confirmClear = true
                        } label: { Text("Clear my answers") }
                    }
                }
            }
            .bcClearScrollBackground()
            .bcTabBarClearance()
            .bcScreenBackground()
            .navigationTitle("Profile")
            .onChange(of: vm.profile) { _, _ in
                if vm.hasChanges && !vm.isSaving { Task { await vm.save() } }
            }
            .onChange(of: vm.isSaving) { _, saving in
                // An answer picked while the previous one was saving.
                if !saving && vm.hasChanges { Task { await vm.save() } }
            }
            .sheet(item: $adding) { addable in
                AddProfileAnswerSheet(vm: vm,
                                      questions: questions.filter { addable.ids.contains($0.id) },
                                      onClose: { adding = nil })
            }
            .confirmationDialog("Clear all your answers?", isPresented: $confirmClear, titleVisibility: .visible) {
                Button("Clear", role: .destructive) { Task { await vm.clearAll() } }
            } message: {
                Text("Your calls will still work, they just won't mention your life.")
            }
            .task { if vm.phase == .idle { await vm.load() } }
        }
    }

    /// Question small, answer large; tap to change, swipe to remove.
    private func answeredRow(_ question: ProfileQuestion) -> some View {
        NavigationLink {
            ProfileChoiceView(vm: vm, question: question)
        } label: {
            VStack(alignment: .leading, spacing: 2) {
                Text(question.title)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                Text(question.answerText(in: vm.profile) ?? "")
                    .font(.body)
            }
            .padding(.vertical, 2)
        }
        .swipeActions {
            Button("Remove", role: .destructive) { question.clear(in: &vm.profile) }
                .tint(Theme.destructive)
        }
    }
}

/// Identifies one presentation of the add sheet.
struct AddableQuestions: Identifiable {
    let id = UUID()
    let ids: [String]
}

/// The open questions by topic. Picking a single answer closes the sheet; a
/// multiple-choice question closes with Done.
struct AddProfileAnswerSheet: View {
    @Bindable var vm: ProfileViewModel
    let questions: [ProfileQuestion]
    let onClose: () -> Void

    var body: some View {
        NavigationStack {
            List {
                ForEach(ProfileTopic.allCases) { topic in
                    let rows = questions.filter { $0.topic == topic }
                    if !rows.isEmpty {
                        Section {
                            ForEach(rows) { question in
                                NavigationLink(question.title) {
                                    ProfileChoiceView(vm: vm, question: question, onDone: onClose)
                                }
                            }
                        } header: {
                            SectionHeader(topic.title)
                        } footer: {
                            Text(topic.footer)
                        }
                    }
                }
            }
            .bcClearScrollBackground()
            .bcScreenBackground()
            .navigationTitle("Add to your profile")
            .bcInlineNavTitle()
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel", action: onClose)
                }
            }
        }
    }
}

/// The answers to one question. Single choice: picking one is the answer.
/// Multiple choice: toggle any, then Done.
struct ProfileChoiceView: View {
    @Bindable var vm: ProfileViewModel
    let question: ProfileQuestion
    /// Called when the question is answered; pops back when nil.
    var onDone: (() -> Void)?
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        List {
            Section {
                ForEach(question.options) { option in
                    Button {
                        question.toggle(option.code, in: &vm.profile)
                        if !question.isMultiple { finish() }
                    } label: {
                        HStack {
                            Text(option.label).foregroundStyle(.primary)
                            Spacer()
                            if question.isSelected(option.code, in: vm.profile) {
                                Image(systemName: "checkmark")
                                    .font(.body.weight(.semibold))
                                    .foregroundStyle(Theme.accent)
                            }
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                }
            } footer: {
                Text(question.isMultiple ? String(localized: "Pick all that apply.") : question.topic.footer)
            }
        }
        .bcClearScrollBackground()
        .bcScreenBackground()
        .navigationTitle(question.title)
        .bcInlineNavTitle()
        .toolbar {
            if question.isMultiple {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done", action: finish)
                }
            }
        }
    }

    private func finish() {
        if let onDone { onDone() } else { dismiss() }
    }
}

/// The sections of the profile, in display order.
enum ProfileTopic: String, CaseIterable, Identifiable {
    case work, home, family, partner, changes, details
    var id: String { rawValue }

    /// The section an alibi's "use details from my profile" module draws on;
    /// the server calls partner and changes "relationship" and "transition".
    init?(contextModule: String) {
        switch contextModule {
        case "relationship": self = .partner
        case "transition": self = .changes
        default: self.init(rawValue: contextModule)
        }
    }

    var title: String {
        switch self {
        case .work: return String(localized: "Work")
        case .home: return String(localized: "Home")
        case .family: return String(localized: "Family")
        case .partner: return String(localized: "Partner")
        case .changes: return String(localized: "Recent changes")
        case .details: return String(localized: "On the call")
        }
    }

    /// What the caller does with the answers.
    var footer: String {
        switch self {
        case .work: return String(localized: "So a caller can say your shift moved or a client needs you.")
        case .home: return String(localized: "For reasons like the landlord coming by or the dog sitter canceling.")
        case .family: return String(localized: "For a relative who suddenly needs you.")
        case .partner: return String(localized: "Tells the caller whether mentioning your partner is fine.")
        case .changes: return String(localized: "Something new, like a job or a move, makes a sudden call easy to believe.")
        case .details: return String(localized: "How much the caller may say about your life, in case others hear the call. \"Keep it vague\" leaves out everything else in your profile.")
        }
    }
}

/// One profile question: its wording, its answers and where the answer lives.
struct ProfileQuestion: Identifiable {
    enum Answer {
        case single(WritableKeyPath<ContextProfile, String?>)
        case multiple(WritableKeyPath<ContextProfile, [String]>)
    }

    let id: String
    let topic: ProfileTopic
    let title: String
    let answer: Answer
    let options: [TemplateOption]

    var isMultiple: Bool {
        if case .multiple = answer { return true }
        return false
    }

    func isAnswered(in profile: ContextProfile) -> Bool {
        switch answer {
        case .single(let path): return profile[keyPath: path] != nil
        case .multiple(let path): return !profile[keyPath: path].isEmpty
        }
    }

    func isSelected(_ code: String, in profile: ContextProfile) -> Bool {
        switch answer {
        case .single(let path): return profile[keyPath: path] == code
        case .multiple(let path): return profile[keyPath: path].contains(code)
        }
    }

    /// Single choice sets the answer; multiple choice adds or removes it.
    func toggle(_ code: String, in profile: inout ContextProfile) {
        switch answer {
        case .single(let path):
            profile[keyPath: path] = code
        case .multiple(let path):
            if profile[keyPath: path].contains(code) {
                profile[keyPath: path].removeAll { $0 == code }
            } else {
                profile[keyPath: path].append(code)
            }
        }
    }

    func clear(in profile: inout ContextProfile) {
        switch answer {
        case .single(let path): profile[keyPath: path] = nil
        case .multiple(let path): profile[keyPath: path] = []
        }
    }

    /// The answer's labels, in the catalog's order.
    func answerText(in profile: ContextProfile) -> String? {
        let labels = options.filter { isSelected($0.code, in: profile) }.map(\.label)
        return labels.isEmpty ? nil : labels.joined(separator: ", ")
    }

    static func all(_ o: ProfileOptions) -> [ProfileQuestion] {
        [
            .init(id: "industry", topic: .work, title: String(localized: "What field do you work in?"),
                  answer: .single(\.workIndustry), options: o.workIndustries),
            .init(id: "role", topic: .work, title: String(localized: "What's your position?"),
                  answer: .single(\.workRoleLevel), options: o.workRoleLevels),
            .init(id: "setting", topic: .work, title: String(localized: "Where do you work?"),
                  answer: .single(\.workSetting), options: o.workSettings),
            .init(id: "schedule", topic: .work, title: String(localized: "When do you work?"),
                  answer: .single(\.workSchedule), options: o.workSchedules),
            .init(id: "travel", topic: .work, title: String(localized: "Do you travel for work?"),
                  answer: .single(\.workTravelScope), options: o.workTravelScopes),
            .init(id: "living", topic: .home, title: String(localized: "Who do you live with?"),
                  answer: .single(\.livingSetup), options: o.livingSetups),
            .init(id: "responsibilities", topic: .home, title: String(localized: "What do you look after?"),
                  answer: .multiple(\.homeResponsibilities), options: o.homeResponsibilities),
            .init(id: "dependents", topic: .home, title: String(localized: "Who depends on you?"),
                  answer: .multiple(\.dependentContexts), options: o.dependentContexts),
            .init(id: "familySupport", topic: .family, title: String(localized: "Do you help your family?"),
                  answer: .single(\.familySupportLevel), options: o.familySupportLevels),
            .init(id: "familyProximity", topic: .family, title: String(localized: "Where does your family live?"),
                  answer: .single(\.familyProximity), options: o.familyProximities),
            .init(id: "relationshipVisibility", topic: .partner, title: String(localized: "Who knows you're together?"),
                  answer: .single(\.relationshipVisibility), options: o.relationshipVisibilities),
            .init(id: "relationshipStage", topic: .partner, title: String(localized: "How long have you been together?"),
                  answer: .single(\.relationshipStage), options: o.relationshipStages),
            .init(id: "transition", topic: .changes, title: String(localized: "Anything new in your life?"),
                  answer: .single(\.transitionState), options: o.transitionStates),
            .init(id: "transitionHorizon", topic: .changes, title: String(localized: "For how long?"),
                  answer: .single(\.transitionHorizon), options: o.transitionHorizons),
            .init(id: "privacy", topic: .details, title: String(localized: "How much about you?"),
                  answer: .single(\.privacyPreference), options: o.privacyPreferences),
        ]
        .filter { !$0.options.isEmpty }
    }
}

struct ProfileView_Previews: PreviewProvider {
    static var previews: some View {
        ProfileView(vm: ProfileViewModel(service: MockContextProfileService(),
                                         templates: MockTemplateService()))
    }
}
#endif
