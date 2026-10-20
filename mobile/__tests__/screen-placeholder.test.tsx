import { render } from '@testing-library/react-native';

import { ScreenPlaceholder } from '@/components/screen-placeholder';

describe('ScreenPlaceholder', () => {
  it('renders its title', async () => {
    const { getByText } = await render(<ScreenPlaceholder title="Dashboard" />);
    expect(getByText('Dashboard')).toBeTruthy();
  });
});
