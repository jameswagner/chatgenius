module.exports = {
  // ... other config
  extend: {
    keyframes: {
      highlight: {
        '0%': { backgroundColor: 'rgb(254 249 195)' },  // yellow-100
        '100%': { backgroundColor: 'transparent' },
      }
    },
    animation: {
      highlight: 'highlight 5s ease-out'
    }
  }
} 