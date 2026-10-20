import AppTabs from '@/components/app-tabs';

/**
 * The signed-in area.
 *
 * The tabs live in their own group so every `NativeTabs.Trigger` stays a
 * sibling of this layout — that is what the navigator resolves `name` against.
 * It also keeps `(auth)` out of the tabs navigator, which would otherwise
 * redirect away from any route no visible trigger declares.
 */
export default function TabsLayout() {
  return <AppTabs />;
}
