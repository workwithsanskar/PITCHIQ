import { X } from 'lucide-react';

export type ActiveFilter = {
  name: string;
  value: string;
  onRemove: () => void;
};

export function ActiveFilters({ items }: { items: ActiveFilter[] }) {
  if (!items.length) return null;

  return <div className="active-filters" role="group" aria-label="Active filters">
    <span className="active-filter-count">{items.length} active</span>
    {items.map(item => <button className="active-filter-chip" type="button" key={item.name}
      aria-label={`Remove ${item.name} filter`} onClick={item.onRemove}>
      <span>{item.name}: <b>{item.value}</b></span><X size={13} aria-hidden="true"/>
    </button>)}
  </div>;
}
