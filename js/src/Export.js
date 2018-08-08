import React from 'react'

const EXPORTS = [
  {
    title: 'Event Export',
    desciption: 'Export information about all events, both past and future.',
    link: '/api/export/events.csv',
    btn: 'Export All Events',
  },
  {
    title: 'Category Export',
    desciption: 'Export information about all event categories.',
    link: '/api/export/categories.csv',
    btn: 'Export All Categories',
  },
  {
    title: 'User Export',
    desciption: 'Export information on all users including name, email and last activity.',
    link: '/api/export/users.csv',
    btn: 'Export All Users',
  },
  {
    title: 'Ticket Export',
    desciption: 'Export information on ticket sales.',
    link: '/api/export/tickets.csv',
    btn: 'Export All Tickets',
  },
]

export default () => (
  EXPORTS.map(e => (
    <div key={e.link} className="mb-4">
      <h2>{e.title}</h2>
      <p>{e.desciption}</p>
      <a href={e.link} download={true} className="btn btn-primary">
        {e.btn}
      </a>
    </div>
  ))
)
