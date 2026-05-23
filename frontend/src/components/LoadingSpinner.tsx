interface LoadingSpinnerProps {
  label?: string;
  inline?: boolean;
}

export function LoadingSpinner({ label, inline = false }: LoadingSpinnerProps) {
  return (
    <div className={inline ? 'spinner spinner--inline' : 'spinner'}>
      <span className="spinner__circle" aria-hidden="true" />
      {label && <span className="spinner__label">{label}</span>}
    </div>
  );
}
