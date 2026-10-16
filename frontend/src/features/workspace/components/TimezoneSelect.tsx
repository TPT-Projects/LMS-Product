import { forwardRef, useMemo } from 'react';

import { Select, type SelectProps } from '@/components/ui/Input';

import { allTimezones } from '../timezones';

export const TimezoneSelect = forwardRef<HTMLSelectElement, SelectProps>(
  function TimezoneSelect(props, ref) {
    const zones = useMemo(allTimezones, []);
    return (
      <Select ref={ref} {...props}>
        {zones.map((zone) => (
          <option key={zone} value={zone}>
            {zone.replaceAll('_', ' ')}
          </option>
        ))}
      </Select>
    );
  },
);
