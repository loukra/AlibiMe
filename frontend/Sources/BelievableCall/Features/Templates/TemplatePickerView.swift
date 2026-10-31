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
                        group(String(localized: "Your alibis"), vm.customTemplates)
                    }
                    ForEach(vm.templatesByCategory, id: \.category) { group in
                        self.group(group.category.title, group.templates)
                    }
                }
                .padding(Spacing.m)
            }
            .bcScreenBackground()
            .navigationTitle("Choose an alibi")
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

/// The same card as a row on the Templates tab, plus a check on the chosen one.
struct TemplateCard: View {
    let template: TemplateSummary
    let isSelected: Bool
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            Card {
                ListCardRow(icon: template.category.systemImage,
                            title: template.displayName,
                            detail: template.description ?? "") {
                    if isSelected {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundStyle(Theme.accent)
                    }
                } footer: {
                    ChannelGlyphs(channels: template.supportedChannels)
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
