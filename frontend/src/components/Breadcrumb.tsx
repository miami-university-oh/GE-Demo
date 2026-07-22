import React from 'react';

export interface Crumb {
  label: string;
  // Ancestor crumbs navigate; the current level has no onClick.
  onClick?: () => void;
}

interface BreadcrumbProps {
  crumbs: Crumb[];
}

export const Breadcrumb: React.FC<BreadcrumbProps> = ({ crumbs }) => {
  return (
    <nav className="breadcrumb" aria-label="Location">
      {crumbs.map((crumb, i) => (
        <React.Fragment key={crumb.label}>
          {i > 0 && <span className="breadcrumb-sep" aria-hidden="true">›</span>}
          {crumb.onClick ? (
            <button type="button" className="breadcrumb-link" onClick={crumb.onClick}>
              {crumb.label}
            </button>
          ) : (
            <span className="breadcrumb-current" aria-current="location">{crumb.label}</span>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
};
