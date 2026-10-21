import { fireEvent, render } from '@testing-library/react-native';

jest.mock('@/api/use-pg', () => ({
  usePg: jest.fn(),
  useUpdatePg: jest.fn(),
}));

import { ApiError } from '@/api/client';
import { usePg, useUpdatePg } from '@/api/use-pg';
import { PgDetailsCard } from '@/components/pg-details-card';
import type { Pg } from '@/types/pg';

const usePgMock = usePg as jest.MockedFunction<typeof usePg>;
const useUpdatePgMock = useUpdatePg as jest.MockedFunction<typeof useUpdatePg>;

const pg: Pg = {
  id: '9b1f0c2a-4e77-4a51-9f3d-0b6a1c8e2d44',
  name: 'Sri Sai PG',
  address: '12, 4th Cross, Koramangala',
  default_rent_due_day: 10,
  created_at: '2026-10-20T09:15:00+05:30',
};

type QueryStub = Partial<ReturnType<typeof usePg>>;

function stubQuery(state: QueryStub) {
  usePgMock.mockReturnValue({
    data: undefined,
    error: null,
    isLoading: false,
    isError: false,
    ...state,
  } as ReturnType<typeof usePg>);
}

beforeEach(() => {
  jest.clearAllMocks();
  useUpdatePgMock.mockReturnValue({
    mutate: jest.fn(),
    reset: jest.fn(),
    isPending: false,
    isError: false,
    error: null,
  } as unknown as ReturnType<typeof useUpdatePg>);
});

/**
 * Render-only, deliberately: no test here submits the form. RNTL 14 + React 19
 * leaves an act() scope open past a react-hook-form submit, which empties the
 * tree for any later render() in the same file — so the save path is covered a
 * level down in `use-update-pg.test.tsx` (the same split F1 used for Login).
 */
describe('PgDetailsCard', () => {
  it('shows the PG name, address and due day, with an Edit button', async () => {
    stubQuery({ data: pg });

    const screen = await render(<PgDetailsCard />);

    expect(screen.getByText('PG DETAILS')).toBeTruthy();
    expect(screen.getByText('Sri Sai PG')).toBeTruthy();
    expect(screen.getByText('12, 4th Cross, Koramangala')).toBeTruthy();
    expect(screen.getByText('Rent due on the 10th of each month')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Edit' })).toBeTruthy();
  });

  it('says so when there is no address yet', async () => {
    stubQuery({ data: { ...pg, address: null } });

    const screen = await render(<PgDetailsCard />);

    expect(screen.getByText('No address yet')).toBeTruthy();
  });

  it('shows a loading line while the PG is being fetched', async () => {
    stubQuery({ isLoading: true });

    const screen = await render(<PgDetailsCard />);

    expect(screen.getByText('Loading…')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull();
  });

  it('maps a failed request to a readable message', async () => {
    stubQuery({ isError: true, error: new Error('Network request failed') });

    const screen = await render(<PgDetailsCard />);

    expect(screen.getByText("Can't reach server. Check your connection.")).toBeTruthy();
  });

  it('shows an empty state on 404 instead of the raw "pg not found"', async () => {
    stubQuery({ isError: true, error: new ApiError(404, 'pg not found') });

    const screen = await render(<PgDetailsCard />);

    expect(screen.getByText('No PG set up yet.')).toBeTruthy();
    expect(screen.getByText('Please contact support.')).toBeTruthy();
    expect(screen.queryByText('Pg not found')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull();
  });

  it('opens an edit form prefilled from the current values', async () => {
    stubQuery({ data: pg });

    const screen = await render(<PgDetailsCard />);
    fireEvent.press(screen.getByRole('button', { name: 'Edit' }));

    // findBy*, not getBy*: the press schedules a re-render that React 19 has
    // not flushed by the time the next line runs.
    expect((await screen.findByLabelText('PG NAME')).props.value).toBe('Sri Sai PG');
    expect(screen.getByLabelText('ADDRESS (OPTIONAL)').props.value).toBe(
      '12, 4th Cross, Koramangala',
    );
    expect(screen.getByLabelText('RENT DUE DAY').props.value).toBe('10');
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeTruthy();
  });
});
