import { Routes, Route } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { CourseDetail } from '@/pages/CourseDetail'
import { Chat } from '@/pages/Chat'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/course/:courseId" element={<CourseDetail />} />
        <Route path="/chat" element={<Chat />} />
      </Routes>
    </Layout>
  )
}

export default App 