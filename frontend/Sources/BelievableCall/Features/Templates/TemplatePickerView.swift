#if canImport(SwiftUI)
import SwiftUI

/// Picker where the user chooses who is contacting them and why. The user's own
/// templates come first, then the built-in ones by category.
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
                    if !vm.customTemplates.isEmpty {
                        group("Your templates", vm.customTemplates)
                    }
                    ForEach(vm.templatesByCategory, id: \.category) { group in
                        self.group(group.category.title, group.templates)
                    }
                }
                .padding(Spacing.m)
            }
            .bcScreenBackground()
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

private extension TemplatePickerView {
    func group(_ title: String, _ templates: [TemplateSummary]) -> some View {
        VStack(alignment: .leading, spacing: Spacing.s) {
            SectionHeader(title)
            ForEach(templates) { template in
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

struct TemplateCard: View {
    let template: TemplateSummary
    let isSelected: Bool
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            Card {
                HStack(alignment: .top, spacing: Spacing.m) {
                    TemplateBadge(category: template.category)
                    VStack(alignment: .leading, spacing: Spacing.s) {
                        HStack(alignment: .firstTextBaseline) {
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
                        // One template, both channel previews — so a dual-channel
                        // template reveals how each channel behaves.
                        VStack(alignment: .leading, spacing: Spacing.xs) {
                            if template.supports(.call), let line = template.previewOpeningLine {
                                channelPreview(.call, text: line)
                            }
                            if template.supports(.text), let body = template.previewSMSBody {
                                channelPreview(.text, text: body)
                            }
                        }
                    }
                }
            }
            .overlay(
                RoundedRectangle(cornerRadius: Radius.card, style: .continuous)
                    .strokeBorder(isSelected ? Theme.accent : Color.clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(isSelected ? [.isButton, .isSelected] : .isButton)
    }

    /// A labelled, per-channel preview line (e.g. CALL “…”, TEXT “…”).
    @ViewBuilder
    private func channelPreview(_ channel: Channel, text: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: Spacing.s) {
            Image(systemName: channel.outlineSymbol)
                .font(.caption)
                .foregroundStyle(.secondary)
                .frame(width: 18)
            Text("“\(text)”")
                .font(.footnote.italic())
                .foregroundStyle(.secondary)
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(channel.title) preview: \(text)")
    }
}

struct TemplatePickerView_Previews: PreviewProvider {
    static var previews: some View {
        TemplatePickerView(vm: HomeViewModel(templateService: MockTemplateService(),
                                             requestService: MockRequestService(),
                                             profileService: MockProfileService(),
                                             prefs: InMemoryPreferences(),
                                             contacts: MockContactsService(),
                                             contactLinks: InMemoryContactLinkStore())) {}
    }
}
#endif
