import { Stack } from 'expo-router';

/** Login and signup, shown while nobody is logged in. */
export default function AuthLayout() {
  return <Stack screenOptions={{ headerShown: false }} />;
}
