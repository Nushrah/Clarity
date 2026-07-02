import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export const useTalentWorkflowStore = create(
  persist(
    (set) => ({
      businessGoal: '',
      teamId: 'team_alpha',
      team: null,
      members: [],
      workflowResult: null,
      managerDecision: null,
      hiringJobId: null,
      // Resume-screening process state — persisted so it survives navigation.
      hiringResumes: [],
      hiringScorecards: [],
      hiringDecisionState: {},

      setTeamContext: ({ team, members, businessGoal }) =>
        set({ team, members, businessGoal: businessGoal || '' }),

      setBusinessGoal: (businessGoal) => set({ businessGoal }),

      setWorkflowResult: (workflowResult) => set({ workflowResult }),

      setManagerDecision: (managerDecision) => set({ managerDecision }),

      setHiringJobId: (hiringJobId) => set({ hiringJobId }),

      setHiringResumes: (hiringResumes) => set({ hiringResumes }),

      setHiringScorecards: (hiringScorecards) => set({ hiringScorecards }),

      setHiringDecisionState: (hiringDecisionState) => set({ hiringDecisionState }),

      clearHiring: () =>
        set({ hiringResumes: [], hiringScorecards: [], hiringDecisionState: {}, hiringJobId: null }),

      clearWorkflow: () =>
        set({ workflowResult: null, managerDecision: null }),
    }),
    {
      name: 'clarity-workflow',
      storage: createJSONStorage(() => ({
        getItem: (name) => {
          try {
            return sessionStorage.getItem(name);
          } catch {
            return null;
          }
        },
        setItem: (name, value) => {
          try {
            sessionStorage.setItem(name, value);
          } catch {
            // ignore quota / private mode errors
          }
        },
        removeItem: (name) => {
          try {
            sessionStorage.removeItem(name);
          } catch {
            // ignore
          }
        },
      })),
      onRehydrateStorage: () => (state, err) => {
        if (err) {
          try {
            sessionStorage.removeItem('clarity-workflow');
          } catch {
            // ignore
          }
        }
      },
    }
  )
);
