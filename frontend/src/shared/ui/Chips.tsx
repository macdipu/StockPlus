interface ChipsProps<K extends string> {
  options: ReadonlyArray<{ key: K; label: string; title?: string }>;
  value: K | null;
  onChange: (key: K) => void;
  label: string;
}

export function Chips<K extends string>({ options, value, onChange, label }: ChipsProps<K>) {
  return (
    <div className="chips" role="group" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.key}
          type="button"
          className={`chip ${o.key === value ? "on" : ""}`}
          aria-pressed={o.key === value}
          title={o.title}
          onClick={() => onChange(o.key)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
