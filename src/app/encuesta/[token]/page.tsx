import { SurveyForm } from '@/components/campanas/SurveyForm';
export default async function Page({params}: {params: Promise<{token:string}>}) {
  const {token}=await params;
  return <SurveyForm token={token}/>;
}
