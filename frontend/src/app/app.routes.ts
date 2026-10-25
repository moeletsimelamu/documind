import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'library' },
  {
    path: 'library',
    title: 'Library · DocuMind',
    loadComponent: () => import('./features/library/library-page').then((m) => m.LibraryPage),
  },
  {
    path: 'documents/:id',
    title: 'Document · DocuMind',
    loadComponent: () => import('./features/reader/document-page').then((m) => m.DocumentPage),
  },
  {
    path: 'search',
    title: 'Search · DocuMind',
    loadComponent: () => import('./features/search/search-page').then((m) => m.SearchPage),
  },
  {
    path: 'ask',
    title: 'Ask · DocuMind',
    loadComponent: () => import('./features/ask/ask-page').then((m) => m.AskPage),
  },
  {
    path: '**',
    title: 'Page not found · DocuMind',
    loadComponent: () => import('./features/not-found-page').then((m) => m.NotFoundPage),
  },
];
