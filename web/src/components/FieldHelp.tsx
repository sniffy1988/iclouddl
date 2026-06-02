type Props = {
  children: React.ReactNode;
  className?: string;
};

/** Muted helper text under a form field. */
export default function FieldHelp({ children, className = "" }: Props) {
  return <p className={`text-xs text-slate-500 mt-1.5 leading-relaxed ${className}`}>{children}</p>;
}

type HelpBoxProps = {
  title?: string;
  children: React.ReactNode;
};

/** Bordered panel for multi-step or longer instructions. */
export function HelpBox({ title, children }: HelpBoxProps) {
  return (
    <div className="rounded-lg border border-slate-700/80 bg-slate-800/40 px-3 py-3 text-xs text-slate-400 leading-relaxed space-y-2">
      {title && <p className="font-medium text-slate-300">{title}</p>}
      {children}
    </div>
  );
}
