#if canImport(SwiftUI)
import SwiftUI

/// Picker where the user chooses who is contacting them and why. Templates are
/// grouped by category; the underlying story is not editable in MVP.
public struct TemplatePickerView: View {
    @Bindable var vm: HomeViewModel
    let onDone: () -> Void

    public init(vm: HomeViewModel, onDone: @escaping () -> Void) {
        self.vm = vm
        self.onDone = onDone
    }

    public var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Spacing.l) {
                    ForEach(vm.templatesByCategory, id: \.category) { group in
                        VStack(alignment: .leading, spacing: Spacing.s) {
                            SectionHeader(group.category.title)
                            ForEach(group.templates) { template in
                                TemplateCard(template: template,
                                             isSelected: template.id == vm.selectedTemplate?.id) {
                                    vm.selectTemplate(template)
                                    Haptics.play(.impact)
                                    onDone()
                                }
                            }
                        }
                    }
                }
                .padding(Spacing.m)
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Choose a template")
            .bcInlineNavTitle()
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done", action: onDone)
                }
            }
        }
    }
}

struct TemplateCard: View {
    let template: TemplateSummary
    let isSelected: Bool
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            Card {
                VStack(alignment: .leading, spacing: Spacing.s) {
                    HStack {
                        Text(template.displayName)
                            .font(.headline)
                            .foregroundStyle(.primary)
                        Spacer()
                        if isSelected {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundStyle(Theme.accent)
                        }
                    }
                    if let description = template.description {
                        Text(description)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    if let preview = template.previewOpeningLine ?? template.previewSMSBody {
                        Text("“\(preview)”")
                            .font(.footnote.italic())
                            .foregroundStyle(.secondary)
                            .lineLimit(2)
                    }
                    HStack(spacing: Spacing.xs) {
                        ForEach(Array(template.supportedChannels).sorted { $0.rawValue < $1.rawValue }) { channel in
                            Label(channel.title, systemImage: channel.systemImage)
                                .font(.caption.weight(.medium))
                                .padding(.horizontal, Spacing.s)
                                .padding(.vertical, 2)
                                .background(Theme.accent.opacity(0.12))
                                .foregroundStyle(Theme.accent)
                                .clipShape(Capsule())
                        }
                    }
                }
            }
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(isSelected ? [.isButton, .isSelected] : .isButton)
    }
}

struct TemplatePickerView_Previews: PreviewProvider {
    static var previews: some View {
        TemplatePickerView(vm: HomeViewModel(templateService: MockTemplateService(),
                                             requestService: MockRequestService(),
                                             profileService: MockProfileService(),
                                             prefs: InMemoryPreferences())) {}
    }
}
#endif
